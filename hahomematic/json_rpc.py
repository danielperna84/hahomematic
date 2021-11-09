import json
import logging
import ssl
import urllib
import urllib.request

from aiohttp import ClientSession

from hahomematic import config
from hahomematic.const import (
    ATTR_ERROR,
    ATTR_PASSWORD,
    ATTR_RESULT,
    ATTR_SESSION_ID,
    ATTR_USERNAME,
    PATH_JSON_RPC,
)

_LOGGER = logging.getLogger(__name__)
VERIFIED_CTX = ssl.create_default_context()
UNVERIFIED_CTX = ssl.create_default_context()
UNVERIFIED_CTX.check_hostname = False
UNVERIFIED_CTX.verify_mode = ssl.CERT_NONE


class JsonRpcAioHttpSession:
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        client,
    ):
        """Session setup."""
        self._client = client
        self._client_session = client.client_session
        self._session_id = None
        self._host = client.host
        self._port = client.json_port
        self._username = client.username
        self._password = client.password
        self._tls = client.json_tls
        self._verify_tls = client.verify_tls

    @property
    def is_activated(self):
        """If session exists, then it is activated."""
        return self._session_id is not None

    async def login_or_renew(self):
        """Renew JSON-RPC session or perform login."""
        if not self.is_activated:
            return await self._login()

        try:
            response = await self.post(
                "Session.renew",
                {ATTR_SESSION_ID: self._session_id},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session_id = response[ATTR_RESULT]
                return True
            return await self._login()
        except Exception:
            _LOGGER.exception(
                "json_rpc.renew: Exception while renewing JSON-RPC session."
            )
            return False

    async def _login(self):
        """Login to CCU and return session."""
        self._session_id = False
        try:
            if self._client_session is None:
                self._client_session = ClientSession(loop=self._client.server.loop)

            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            response = await self.post(
                method="Session.login", extra_params=params, use_default_params=False
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session_id = response[ATTR_RESULT]

            if not self._session_id:
                _LOGGER.warning(
                    "json_rpc.login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return False
            return True
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception("json_rpc.login: Exception while logging in via JSON-RPC")
            return False

    async def post(self, method, extra_params=None, use_default_params=True):
        """Reusable JSON-RPC POST function."""
        params = self._get_params(extra_params, use_default_params)

        _LOGGER.debug("helpers.json_rpc.post: Method: %s", method)
        try:
            payload = json.dumps(
                {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
            ).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Content-Length": len(payload),
            }

            _LOGGER.debug("helpers.json_rpc.post: API-Endpoint: %s", self._url)
            req = urllib.request.Request(self._url, payload, headers)
            if self._tls:
                if self._verify_tls:
                    resp = await self._client_session.post(
                        self._url,
                        data=payload,
                        timeout=config.TIMEOUT,
                        context=VERIFIED_CTX,
                    )
                else:
                    resp = await self._client_session.post(
                        self._url,
                        data=payload,
                        timeout=config.TIMEOUT,
                        context=UNVERIFIED_CTX,
                    )
            else:
                resp = await self._client_session.post(
                    self._url, data=payload, timeout=config.TIMEOUT
                )
            if resp.status == 200:
                try:
                    return await json.loads(resp.json(encoding="utf-8"))
                except ValueError:
                    _LOGGER.exception(
                        "helpers.json_rpc.post: Failed to parse JSON. Trying workaround."
                    )
                    # Workaround for bug in CCU
                    return json.loads(resp.json(encoding="utf-8").replace("\\", ""))
            else:
                _LOGGER.error("helpers.json_rpc.post: Status: %i", resp.status)
                return {"error": resp.status, "result": {}}
        # pylint: disable=broad-except
        except Exception as err:
            _LOGGER.exception("helpers.json_rpc.post: Exception")
            return {"error": str(err), "result": {}}

    async def logout(self):
        """Logout of CCU."""
        if not self._session_id:
            _LOGGER.warning("json_rpc.logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": self._session_id}
            response = await self.post(
                "Session.logout",
                params,
            )
            if response[ATTR_ERROR]:
                _LOGGER.warning(
                    "json_rpc.logout: Logout error: %s", response[ATTR_RESULT]
                )
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "json_rpc.logout: Exception while logging in via JSON-RPC"
            )
        return

    def _get_params(self, extra_params, use_default_params) -> dict[str, str]:
        """Add additional params to default prams."""
        params = {"_session_id_": self._session_id} if use_default_params else {}
        if extra_params:
            params.update(extra_params)
        return params

    @property
    def _url(self):
        """Return the required url."""
        if self._tls:
            return f"https://{self._host}:{self._port}{PATH_JSON_RPC}"
        return f"http://{self._host}:{self._port}{PATH_JSON_RPC}"


class JsonRpcSession:
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        client,
    ):
        """Session setup."""
        self._client = client
        self._session_id = None
        self._host = client.host
        self._port = client.json_port
        self._username = client.username
        self._password = client.password
        self._tls = client.tls
        self._verify_tls = client.verify_tls

    @property
    def is_activated(self):
        """If session exists, then it is activated."""
        return self._session_id is not None

    async def login_or_renew(self):
        """Renew JSON-RPC session or perform login."""
        if not self._session_id:
            return await self._login()

        try:
            response = await self.post(
                "Session.renew",
                {ATTR_SESSION_ID: self._session_id},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session_id = response[ATTR_RESULT]
                return True
            return await self._login()
        except Exception:
            _LOGGER.exception(
                "json_rpc.renew: Exception while renewing JSON-RPC session."
            )
            return False

    async def _login(self):
        """Login to CCU and return session."""
        self._session_id = False
        try:
            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            response = await self.post(
                method="Session.login", extra_params=params, use_default_params=False
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session_id = response[ATTR_RESULT]

            if not self._session_id:
                _LOGGER.warning(
                    "json_rpc.login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return False
            return True
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception("json_rpc.login: Exception while logging in via JSON-RPC")
            return False

    async def post(self, method, extra_params=None, use_default_params=True):
        params = self._get_params(extra_params, use_default_params)

        def _post():
            """Reusable JSON-RPC POST function."""
            _LOGGER.debug("helpers.json_rpc.post: Method: %s", method)
            try:
                payload = json.dumps(
                    {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
                ).encode("utf-8")

                headers = {
                    "Content-Type": "application/json",
                    "Content-Length": len(payload),
                }
                _LOGGER.debug("helpers.json_rpc.post: API-Endpoint: %s", self._url)
                req = urllib.request.Request(self._url, payload, headers)
                if self._tls:
                    if self._verify_tls:
                        resp = urllib.request.urlopen(
                            req, timeout=config.TIMEOUT, context=VERIFIED_CTX
                        )
                    else:
                        resp = urllib.request.urlopen(
                            req, timeout=config.TIMEOUT, context=UNVERIFIED_CTX
                        )
                else:
                    resp = urllib.request.urlopen(req, timeout=config.TIMEOUT)
                if resp.status == 200:
                    try:
                        return json.loads(resp.read().decode("utf-8"))
                    except ValueError:
                        _LOGGER.exception(
                            "helpers.json_rpc.post: Failed to parse JSON. Trying workaround."
                        )
                        # Workaround for bug in CCU
                        return json.loads(resp.read().decode("utf-8").replace("\\", ""))
                else:
                    _LOGGER.error("helpers.json_rpc.post: Status: %i", resp.status)
                    return {"error": resp.status, "result": {}}
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.exception("helpers.json_rpc.post: Exception")
                return {"error": str(err), "result": {}}

        return await self._client.server.async_add_json_executor_job(_post)

    async def logout(self):
        """Logout of CCU."""
        if not self._session_id:
            _LOGGER.warning("json_rpc.logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": self._session_id}
            response = await self.post(
                "Session.logout",
                params,
            )
            if response[ATTR_ERROR]:
                _LOGGER.warning(
                    "json_rpc.logout: Logout error: %s", response[ATTR_RESULT]
                )
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "json_rpc.logout: Exception while logging in via JSON-RPC"
            )
        return

    def _get_params(self, extra_params, use_default_params) -> dict[str, str]:
        """Add additional params to default prams."""
        params = {"_session_id_": self._session_id} if use_default_params else {}
        if extra_params:
            params.update(extra_params)
        return params

    @property
    def _url(self):
        """Return the required url."""
        if self._tls:
            return f"https://{self._host}:{self._port}{PATH_JSON_RPC}"
        return f"http://{self._host}:{self._port}{PATH_JSON_RPC}"
