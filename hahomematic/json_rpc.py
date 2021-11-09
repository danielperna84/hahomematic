import logging
import json
import urllib
import urllib.request
import ssl
from hahomematic import config
from aiohttp import ClientSession
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


class JsonRpcSession:
    def __init__(
        self,
        client,
        host: str,
        port: int,
        username: str,
        password: str,
        tls: bool = False,
        verify_tls: bool = False,
    ):
        """Session setup."""
        self._client = client
        self._session = None
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._tls = tls
        self._verify_tls = verify_tls

    @property
    def is_activated(self):
        """If session exists, then it is activated."""
        return self._session is not None

    async def _login(self):
        """Login to CCU and return session."""
        self._session = False
        try:
            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            response = await self.post(
                method="Session.login",
                extra_params=params,
                use_default_params=False
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session = response[ATTR_RESULT]

            if not self._session:
                _LOGGER.warning(
                    "json_rpc.login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return False
            return True
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception("json_rpc.login: Exception while logging in via JSON-RPC")
            return False

    async def logout(self):
        """Logout of CCU."""
        if not self._session:
            _LOGGER.warning("json_rpc.logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": self._session}
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

    async def renew(self):
        """Renew JSON-RPC session or perform login."""
        if not self._session:
            return await self._login()

        try:
            response = await self.post(
                "Session.renew",
                {ATTR_SESSION_ID: self._session},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self._session = response[ATTR_RESULT]
                return True
            return await self._login()
        except Exception:
            _LOGGER.exception(
                "json_rpc.renew: Exception while renewing JSON-RPC session."
            )
            return False

    def _get_params(self, extra_params,use_default_params) -> dict[str, str]:
        """Add additional params to default prams."""
        params = {"_session_id_": self._session} if use_default_params else {}
        if extra_params:
            params.update(extra_params)
        return params

    async def post(
        self,
        method,
        extra_params=None,
        use_default_params=True
    ):
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
                if self._tls:
                    api_endpoint = f"https://{self._host}:{self._port}{PATH_JSON_RPC}"
                else:
                    api_endpoint = f"http://{self._host}:{self._port}{PATH_JSON_RPC}"
                _LOGGER.debug("helpers.json_rpc.post: API-Endpoint: %s", api_endpoint)
                req = urllib.request.Request(api_endpoint, payload, headers)
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
