"""
Implementation of an async json-rpc client.
"""
from __future__ import annotations

from datetime import datetime
import json
import logging
import os
from pathlib import Path
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
    DEFAULT_ENCODING,
    PATH_JSON_RPC,
    REGA_SCRIPT_PATH,
)
from hahomematic.exceptions import BaseHomematicException, HaHomematicException
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
        self._last_session_id_refresh: datetime | None = None
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
            self._last_session_id_refresh = datetime.now()
            return self._session_id is not None
        if self._session_id:
            self._session_id = await self._renew_login(self._session_id)
        return self._session_id is not None

    async def _renew_login(self, session_id: str) -> str | None:
        """Renew JSON-RPC session or perform login."""
        try:
            if self._updated_within_seconds():
                return session_id
            method = "Session.renew"
            response = await self._post(
                session_id=session_id,
                method=method,
                extra_params={ATTR_SESSION_ID: session_id},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                if response[ATTR_RESULT] is True:
                    self._last_session_id_refresh = datetime.now()
                    _LOGGER.debug("_renew_login: Method: %s [%s]", method, session_id)
                    return session_id
            return await self._login()
        except ClientError as cer:
            _LOGGER.error(
                "renew: ClientError [%s] while renewing JSON-RPC session", cer.args
            )
            return None

    def _updated_within_seconds(self, age_seconds: int = 90) -> bool:
        """Check if session id has been updated within 90 seconds."""
        if self._last_session_id_refresh is None:
            return False
        delta = datetime.now() - self._last_session_id_refresh
        if delta.seconds < age_seconds:
            return True
        return False

    async def _login(self) -> str | None:
        """Login to CCU and return session."""
        session_id: str | None = None
        try:
            if not self._username:
                _LOGGER.warning("_post: No username set.")
                return None
            if not self._password:
                _LOGGER.warning("_post: No password set.")
                return None

            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            method = "Session.login"
            response = await self._post(
                session_id=False,
                method=method,
                extra_params=params,
                use_default_params=False,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                session_id = response[ATTR_RESULT]

            _LOGGER.debug("_login: Method: %s [%s]", method, session_id)

            if not session_id:
                _LOGGER.warning(
                    "login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return None
            return session_id
        except BaseHomematicException as hhe:
            _LOGGER.error(
                "login: %s [%s] while logging in via JSON-RPC", hhe.name, hhe.args
            )
            return None

    async def post(
        self,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if keep_session:
            await self.login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._login()

        if not session_id:
            _LOGGER.warning("post: Error while logging in via JSON-RPC.")
            return {"error": "Unable to open session.", "result": {}}

        _LOGGER.debug("post: Method: %s, [%s]", method, extra_params)
        result = await self._post(
            session_id=session_id,
            method=method,
            extra_params=extra_params,
            use_default_params=use_default_params,
        )

        if not keep_session:
            await self._logout(session_id=session_id)
        return result

    async def post_script(
        self,
        script_name: str,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST_SCRIPT function."""
        if keep_session:
            await self.login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._login()

        if not session_id:
            _LOGGER.warning("post_script: Error while logging in via JSON-RPC.")
            return {"error": "Unable to open session.", "result": {}}

        source_path = Path(__file__).resolve()
        script_file = os.path.join(source_path.parent, REGA_SCRIPT_PATH, script_name)
        script = Path(script_file).read_text(encoding=DEFAULT_ENCODING)

        method = "ReGa.runScript"
        result = await self._post(
            session_id=session_id,
            method=method,
            extra_params={"script": script},
        )
        _LOGGER.debug("post_script: Method: %s [%s]", method, script_name)

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
            no_username = "_post: No username set."
            _LOGGER.warning(no_username)
            return {"error": str(no_username), "result": {}}
        if not self._password:
            no_password = "_post: No password set."
            _LOGGER.warning(no_password)
            return {"error": str(no_password), "result": {}}

        params = _get_params(session_id, extra_params, use_default_params)

        try:
            payload = json.dumps(
                {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
            ).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            }

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
                except ValueError as ver:
                    _LOGGER.error(
                        "_post: ValueError [%s] Failed to parse JSON. Trying workaround",
                        ver.args,
                    )
                    # Workaround for bug in CCU
                    return json.loads(
                        (await resp.json(encoding="utf-8")).replace("\\", "")
                    )
            else:
                _LOGGER.warning("_post: Status: %i", resp.status)
                return {"error": resp.status, "result": {}}
        except ClientConnectorError as err:
            _LOGGER.error("_post: ClientConnectorError")
            return {"error": str(err), "result": {}}
        except ClientError as cce:
            _LOGGER.error("_post: ClientError")
            return {"error": str(cce), "result": {}}
        except TypeError as ter:
            _LOGGER.error("_post: TypeError")
            return {"error": str(ter), "result": {}}
        except OSError as oer:
            _LOGGER.error("_post: OSError")
            return {"error": str(oer), "result": {}}
        except Exception as ex:
            raise HaHomematicException from ex

    async def logout(self) -> None:
        """Logout of CCU."""
        await self._logout(self._session_id)

    async def _logout(self, session_id: str | None) -> None:
        """Logout of CCU."""
        if not session_id:
            _LOGGER.debug("_logout: Not logged in. Not logging out.")
            return
        try:
            method = "Session.logout"
            params = {"_session_id_": session_id}
            response = await self._post(
                session_id=session_id,
                method=method,
                extra_params=params,
            )
            _LOGGER.debug("_logout: Method: %s [%s]", method, session_id)
            if response[ATTR_ERROR]:
                _LOGGER.warning("logout: Logout error: %s", response[ATTR_RESULT])
        except ClientError as cer:
            _LOGGER.error(
                "logout: ClientError [%s] while logging in via JSON-RPC", cer.args
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
