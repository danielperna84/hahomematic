"""
Implementation of an async json-rpc client.
"""
from __future__ import annotations

import json
import logging
import ssl
from typing import Any

from aiohttp import ClientConnectorError, ClientError, ClientSession, TCPConnector

from hahomematic import config
import hahomematic.central_unit as hm_central
from hahomematic.const import (
    ATTR_ERROR,
    ATTR_PASSWORD,
    ATTR_RESULT,
    ATTR_SESSION_ID,
    ATTR_USERNAME,
    PATH_JSON_RPC,
)
from hahomematic.helpers import get_tls_context

_LOGGER = logging.getLogger(__name__)


class JsonRpcAioHttpClient:
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        central_config: hm_central.CentralConfig,
    ):
        """Session setup."""
        self._central_config = central_config
        if self._central_config.client_session:
            self._client_session = self._central_config.client_session
        else:
            conn = TCPConnector(limit=3)
            self._client_session = ClientSession(
                connector=conn, loop=self._central_config.loop
            )
        self._session_id: str | None = None
        self._username: str = self._central_config.username
        self._password: str | None = self._central_config.password
        self._tls: bool = self._central_config.tls
        self._tls_context: ssl.SSLContext = get_tls_context(
            self._central_config.verify_tls
        )
        self._url = f"{self._central_config.device_url}{PATH_JSON_RPC}"

    @property
    def is_activated(self) -> bool:
        """If session exists, then it is activated."""
        return self._session_id is not None

    async def login_or_renew(self) -> bool:
        """Renew JSON-RPC session or perform login."""
        if not self.is_activated:
            self._session_id = await self._login()
            return self._session_id is not None
        if self._session_id:
            self._session_id = await self._renew_login(self._session_id)
        return self._session_id is not None

    async def _renew_login(self, session_id: str) -> str | None:
        """Renew JSON-RPC session or perform login."""
        try:
            response = await self._post(
                session_id=session_id,
                method="Session.renew",
                extra_params={ATTR_SESSION_ID: session_id},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                return str(response[ATTR_RESULT])
            return await self._login()
        except ClientError:
            _LOGGER.exception(
                "json_rpc.renew: Exception while renewing JSON-RPC session."
            )
            return None

    async def _login(self) -> str | None:
        """Login to CCU and return session."""
        session_id: str | None = None
        try:
            if not self._username:
                _LOGGER.warning("json_rpc_client._post: No username set.")
                return None
            if not self._password:
                _LOGGER.warning("json_rpc_client._post: No password set.")
                return None

            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            response = await self._post(
                session_id=False,
                method="Session.login",
                extra_params=params,
                use_default_params=False,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                session_id = response[ATTR_RESULT]

            if not session_id:
                _LOGGER.warning(
                    "json_rpc.login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return None
            return session_id
        except Exception:
            _LOGGER.exception("json_rpc.login: Exception while logging in via JSON-RPC")
            return None

    async def post(
        self,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
        keep_session: bool = False,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if keep_session:
            await self.login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._login()

        if not session_id:
            _LOGGER.exception("json_rpc.post: Exception while logging in via JSON-RPC.")
            return {"error": "Unable to open session.", "result": {}}

        result = await self._post(
            session_id=session_id,
            method=method,
            extra_params=extra_params,
            use_default_params=use_default_params,
        )

        if not keep_session:
            await self._logout(session_id=session_id)
        return result

    async def _post(
        self,
        session_id: bool | str,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if not self._username:
            no_username = "json_rpc_client._post: No username set."
            _LOGGER.warning(no_username)
            return {"error": str(no_username), "result": {}}
        if not self._password:
            no_password = "json_rpc_client._post: No password set."
            _LOGGER.warning(no_password)
            return {"error": str(no_password), "result": {}}

        params = _get_params(session_id, extra_params, use_default_params)

        _LOGGER.debug("json_rpc_client._post: Method: %s", method)
        try:
            payload = json.dumps(
                {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
            ).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            }

            _LOGGER.debug("json_rpc_client._post: API-Endpoint: %s", self._url)
            if self._tls:
                resp = await self._client_session.post(
                    self._url,
                    data=payload,
                    headers=headers,
                    timeout=config.TIMEOUT,
                    ssl=self._tls_context,
                )
            else:
                resp = await self._client_session.post(
                    self._url, data=payload, headers=headers, timeout=config.TIMEOUT
                )
            if resp.status == 200:
                try:
                    return await resp.json(encoding="utf-8")
                except ValueError:
                    _LOGGER.exception(
                        "json_rpc_client._post: Failed to parse JSON. Trying workaround."
                    )
                    # Workaround for bug in CCU
                    return json.loads(
                        (await resp.json(encoding="utf-8")).replace("\\", "")
                    )
            else:
                _LOGGER.error("json_rpc_client._post: Status: %i", resp.status)
                return {"error": resp.status, "result": {}}
        except ClientConnectorError as err:
            _LOGGER.exception("json_rpc_client._post: ClientConnectorError")
            return {"error": str(err), "result": {}}
        except ClientError as cce:
            _LOGGER.exception("json_rpc_client._post: ClientError")
            return {"error": str(cce), "result": {}}
        except TypeError as ter:
            _LOGGER.exception("json_rpc_client._post: TypeError")
            return {"error": str(ter), "result": {}}

    async def logout(self) -> None:
        """Logout of CCU."""
        await self._logout(self._session_id)

    async def _logout(self, session_id: str | None) -> None:
        """Logout of CCU."""
        if not session_id:
            _LOGGER.warning("json_rpc.logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": session_id}
            response = await self._post(
                session_id=session_id,
                method="Session.logout",
                extra_params=params,
            )
            if response[ATTR_ERROR]:
                _LOGGER.warning(
                    "json_rpc.logout: Logout error: %s", response[ATTR_RESULT]
                )
        except ClientError:
            _LOGGER.exception(
                "json_rpc.logout: Exception while logging in via JSON-RPC"
            )
        return


def _get_params(
    session_id: bool | str,
    extra_params: dict[str, Any] | None,
    use_default_params: bool,
) -> dict[str, Any]:
    """Add additional params to default prams."""
    params: dict[str, Any] = {"_session_id_": session_id} if use_default_params else {}
    if extra_params:
        params.update(extra_params)
    return params
