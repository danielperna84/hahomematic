# pylint: disable=line-too-long,broad-except,inconsistent-return-statements
"""
The client-object and its methods.
"""
import json
import logging
import socket
import ssl
import time
import urllib
import urllib.request

from hahomematic import config
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CHANNELS,
    ATTR_ERROR,
    ATTR_HM_ADDRESS,
    ATTR_HM_NAME,
    ATTR_HM_PARAMSETS,
    ATTR_INTERFACE,
    ATTR_NAME,
    ATTR_PASSWORD,
    ATTR_PORT,
    ATTR_RESULT,
    ATTR_SESSION_ID,
    ATTR_USERNAME,
    ATTR_VALUE,
    BACKEND_CCU,
    BACKEND_HOMEGEAR,
    DEFAULT_CONNECT,
    DEFAULT_JSON_PORT,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PATH,
    DEFAULT_TLS,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_TLS,
    LOCALHOST,
    PATH_JSON_RPC,
    PORT_RFD,
    PROXY_DE_INIT_FAILED,
    PROXY_DE_INIT_SKIPPED,
    PROXY_DE_INIT_SUCCESS,
    PROXY_INIT_FAILED,
    PROXY_INIT_SKIPPED,
    PROXY_INIT_SUCCESS,
    RELEVANT_PARAMSETS,
)
from hahomematic.helpers import build_api_url, parse_ccu_sys_var
from hahomematic.proxy import ThreadPoolServerProxy

VERIFIED_CTX = ssl.create_default_context()
UNVERIFIED_CTX = ssl.create_default_context()
UNVERIFIED_CTX.check_hostname = False
UNVERIFIED_CTX.verify_mode = ssl.CERT_NONE
_LOGGER = logging.getLogger(__name__)


class ClientException(Exception):
    """hahomematic Client exception."""


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class Client:
    """
    Client object that initializes the XML-RPC proxy
    and provides access to other data via XML-RPC
    or JSON-RPC.
    """

    # pylint: disable=too-many-arguments,too-many-locals,too-many-statements,too-many-branches
    def __init__(
        self,
        server,
        name=DEFAULT_NAME,
        host=LOCALHOST,
        port=PORT_RFD,
        path=DEFAULT_PATH,
        username=DEFAULT_USERNAME,
        password=DEFAULT_PASSWORD,
        tls=DEFAULT_TLS,
        verify_tls=DEFAULT_VERIFY_TLS,
        # connect -> do init
        connect=DEFAULT_CONNECT,
        callback_host=None,
        callback_port=None,
        json_port=DEFAULT_JSON_PORT,
        json_tls=DEFAULT_TLS,
    ):
        """
        Initialize the Client.
        """
        self.server = server
        # Referred to as 'remote' in other places
        self.name = name
        # This is the actual interface_id used for init
        # pylint: disable=invalid-name
        self.interface_id = f"{server.instance_name}-{name}"
        self.host = host
        self.port = port
        self.json_port = json_port
        self.connect = connect
        self.path = path
        self.password = password
        if self.password is None:
            self.username = None
        else:
            self.username = username
        self.tls = tls
        self.json_tls = json_tls
        self.verify_tls = verify_tls
        try:
            socket.gethostbyname(self.host)
        # pylint: disable=broad-except
        except Exception as err:
            _LOGGER.warning("Can't resolve host for %s: %s", self.name, self.host)
            raise ClientException(err) from err
        tmpsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tmpsocket.settimeout(config.TIMEOUT)
        tmpsocket.connect((self.host, self.port))
        self.local_ip = tmpsocket.getsockname()[0]
        tmpsocket.close()
        _LOGGER.debug("Got local ip: %s", self.local_ip)

        # Get callback address
        if callback_host is not None:
            self.callback_host = callback_host
        else:
            self.callback_host = self.local_ip
        if callback_port is not None:
            self.callback_port = int(callback_port)
        else:
            self.callback_port = self.server.local_port
        self.init_url = f"http://{self.callback_host}:{self.callback_port}"
        self.api_url = build_api_url(
            self.host,
            self.port,
            self.path,
            username=self.username,
            password=self.password,
            tls=self.tls,
        )
        self.proxy = ThreadPoolServerProxy(
            self.server.async_add_proxy_executor_job,
            self.api_url,
            tls=self.tls,
            verify_tls=self.verify_tls,  # , loop=self.server.loop
        )
        self.time_initialized = 0
        self.version = None
        self.backend = None
        self.session = None

        self.server.clients[self.interface_id] = self
        if self.init_url not in self.server.clients_by_init_url:
            self.server.clients_by_init_url[self.init_url] = []
        self.server.clients_by_init_url[self.init_url].append(self)

    async def proxy_init(self) -> int:
        """
        To receive events the proxy has to tell the CCU / Homegear
        where to send the events. For that we call the init-method.
        """
        try:
            self.version = await self.proxy.getVersion()
        except Exception as err:
            raise Exception(
                f"Failed to get backend version. Not creating client: {self.name}"
            ) from err
        if "Homegear" in self.version or "pydevccu" in self.version:
            self.backend = BACKEND_HOMEGEAR
            self.session = None
        else:
            self.backend = BACKEND_CCU
            self.session = False

        if not self.connect:
            _LOGGER.debug("proxy_init: Skipping init for %s", self.name)
            return PROXY_INIT_SKIPPED
        if self.server is None:
            _LOGGER.warning("proxy_init: Local server missing for %s", self.name)
            self.time_initialized = 0
            return PROXY_INIT_FAILED
        try:
            _LOGGER.debug(
                "proxy_init: init('%s', '%s')", self.init_url, self.interface_id
            )
            await self.proxy.init(self.init_url, self.interface_id)
            _LOGGER.info("proxy_init: Proxy for %s initialized", self.name)
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "proxy_init: Failed to initialize proxy for %s", self.name
            )
            self.time_initialized = 0
            return PROXY_INIT_FAILED
        self.time_initialized = int(time.time())
        return PROXY_INIT_SUCCESS

    async def proxy_de_init(self) -> int:
        """
        De-init to stop CCU from sending events for this remote.
        """
        if self.session:
            await self.json_rpc_logout()
        if not self.connect:
            _LOGGER.debug("proxy_de_init: Skipping de-init for %s", self.name)
            return PROXY_DE_INIT_SKIPPED
        if self.server is None:
            _LOGGER.warning("proxy_de_init: Local server missing for %s", self.name)
            return PROXY_DE_INIT_FAILED
        if not self.time_initialized:
            _LOGGER.debug(
                "proxy_de_init: Skipping de-init for %s (not initialized)", self.name
            )
            return PROXY_DE_INIT_SKIPPED
        try:
            _LOGGER.debug("proxy_de_init: init('%s')", self.init_url)
            await self.proxy.init(self.init_url)
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "proxy_de_init: Failed to de-initialize proxy for %s", self.name
            )
            return PROXY_DE_INIT_FAILED
        # TODO: Should the de-init really be skipped for other clients?
        #  for client in server.clients_by_init_url.get(self.init_url, []):
        #     _LOGGER.debug("proxy_de_init: Setting client %s initialized status to False.", client.id)
        #     client.initialized = False
        self.time_initialized = 0
        return PROXY_DE_INIT_SUCCESS

    async def proxy_re_init(self) -> int:
        """Reinit Proxy"""
        de_init_status = await self.proxy_de_init()
        if de_init_status is not PROXY_DE_INIT_FAILED:
            return await self.proxy_init()

    async def json_rpc_login(self):
        """Login to CCU and return session."""
        self.session = False
        try:
            params = {
                ATTR_USERNAME: self.username,
                ATTR_PASSWORD: self.password,
            }
            response = await self.json_rpc_post(
                self.host,
                self.json_port,
                "Session.login",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self.session = response[ATTR_RESULT]

            if not self.session:
                _LOGGER.warning(
                    "json_rpc_login: Unable to open session: %s", response[ATTR_ERROR]
                )
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception("json_rpc_login: Exception while logging in via JSON-RPC")

    async def json_rpc_renew(self):
        """Renew JSON-RPC session or perform login."""
        if not self.session:
            await self.json_rpc_login()
            return

        try:
            response = await self.json_rpc_post(
                self.host,
                self.json_port,
                "Session.renew",
                {ATTR_SESSION_ID: self.session},
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                self.session = response[ATTR_RESULT]
                return
            await self.json_rpc_login()
        except Exception:
            _LOGGER.exception(
                "json_rpc_renew: Exception while renewing JSON-RPC session."
            )

    async def json_rpc_logout(self):
        """Logout of CCU."""
        if not self.session:
            _LOGGER.warning("json_rpc_logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": self.session}
            response = await self.json_rpc_post(
                self.host,
                self.json_port,
                "Session.logout",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )
            if response[ATTR_ERROR]:
                _LOGGER.warning(
                    "json_rpc_logout: Logout error: %s", response[ATTR_RESULT]
                )
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "json_rpc_logout: Exception while logging in via JSON-RPC"
            )
        return

    async def json_rpc_post(
        self,
        host,
        json_port,
        method,
        params=None,
        tls=DEFAULT_TLS,
        verify_tls=DEFAULT_VERIFY_TLS,
    ):
        if params is None:
            params = {}

        def _sync_json_rpc_post():
            """Reusable JSON-RPC POST function."""
            _LOGGER.debug("helpers.json_rpc_post: Method: %s", method)
            try:
                payload = json.dumps(
                    {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
                ).encode("utf-8")

                headers = {
                    "Content-Type": "application/json",
                    "Content-Length": len(payload),
                }
                if tls:
                    api_endpoint = f"https://{host}:{json_port}{PATH_JSON_RPC}"
                else:
                    api_endpoint = f"http://{host}:{json_port}{PATH_JSON_RPC}"
                _LOGGER.debug("helpers.json_rpc_post: API-Endpoint: %s", api_endpoint)
                req = urllib.request.Request(api_endpoint, payload, headers)
                if tls:
                    if verify_tls:
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
                            "helpers.json_rpc_post: Failed to parse JSON. Trying workaround."
                        )
                        # Workaround for bug in CCU
                        return json.loads(resp.read().decode("utf-8").replace("\\", ""))
                else:
                    _LOGGER.error("helpers.json_rpc_post: Status: %i", resp.status)
                    return {"error": resp.status, "result": {}}
            # pylint: disable=broad-except
            except Exception as err:
                _LOGGER.exception("helpers.json_rpc_post: Exception")
                return {"error": str(err), "result": {}}

        return await self.server.async_add_json_executor_job(_sync_json_rpc_post)

    async def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        variables = {}
        if self.backend == BACKEND_CCU and self.username and self.password:
            _LOGGER.debug(
                "get_all_system_variables: Getting all System variables via JSON-RPC"
            )
            await self.json_rpc_renew()
            if not self.session:
                return variables
            try:
                params = {"_session_id_": self.session}
                response = await self.json_rpc_post(
                    self.host,
                    self.json_port,
                    "SysVar.getAll",
                    params,
                    tls=self.json_tls,
                    verify_tls=self.verify_tls,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    for var in response[ATTR_RESULT]:
                        key, value = parse_ccu_sys_var(var)
                        variables[key] = value

            except Exception:
                _LOGGER.exception("get_all_system_variables: Exception")
        else:
            try:
                variables = await self.proxy.getAllSystemVariables()
            except Exception:
                _LOGGER.exception("get_all_system_variables: Exception")
        return variables

    async def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        var = None
        if self.backend == BACKEND_CCU and self.username and self.password:
            _LOGGER.debug("get_system_variable: Getting System variable via JSON-RPC")
            await self.json_rpc_renew()
            if not self.session:
                return var
            try:
                params = {"_session_id_": self.session, ATTR_NAME: name}
                response = await self.json_rpc_post(
                    self.host,
                    self.json_port,
                    "SysVar.getValueByName",
                    params,
                    tls=self.json_tls,
                    verify_tls=self.verify_tls,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    # TODO: This does not yet support strings
                    try:
                        var = float(response[ATTR_RESULT])
                    except Exception:
                        var = response[ATTR_RESULT] == "true"

            except Exception:
                _LOGGER.exception("get_system_variable: Exception")
        else:
            try:
                var = await self.proxy.getSystemVariable(name)
            except Exception:
                _LOGGER.exception("get_system_variable: Exception")
        return var

    async def delete_system_variable(self, name):
        """Delete a system variable from CCU / Homegear."""
        if self.backend == BACKEND_CCU and self.username and self.password:
            _LOGGER.debug(
                "delete_system_variable: Getting System variable via JSON-RPC"
            )
            await self.json_rpc_renew()
            if not self.session:
                return
            try:
                params = {"_session_id_": self.session, ATTR_NAME: name}
                response = await self.json_rpc_post(
                    self.host,
                    self.json_port,
                    "SysVar.deleteSysVarByName",
                    params,
                    tls=self.json_tls,
                    verify_tls=self.verify_tls,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    deleted = response[ATTR_RESULT]
                    _LOGGER.warning("delete_system_variable: Deleted: %s", str(deleted))

            except Exception:
                _LOGGER.exception("delete_system_variable: Exception")
        else:
            try:
                return await self.proxy.deleteSystemVariable(name)
            except Exception:
                _LOGGER.exception("delete_system_variable: Exception")

    async def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        if self.backend == BACKEND_CCU and self.username and self.password:
            _LOGGER.debug("set_system_variable: Setting System variable via JSON-RPC")
            await self.json_rpc_renew()
            if not self.session:
                return
            try:
                params = {
                    "_session_id_": self.session,
                    ATTR_NAME: name,
                    ATTR_VALUE: value,
                }
                if value is True or value is False:
                    params[ATTR_VALUE] = int(value)
                    response = await self.json_rpc_post(
                        self.host, self.json_port, "SysVar.setBool", params
                    )
                else:
                    response = await self.json_rpc_post(
                        self.host, self.json_port, "SysVar.setFloat", params
                    )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    res = response[ATTR_RESULT]
                    _LOGGER.debug(
                        "set_system_variable: Result while setting variable: %s",
                        str(res),
                    )
                else:
                    if response[ATTR_ERROR]:
                        _LOGGER.debug(
                            "set_system_variable: Error while setting variable: %s",
                            str(response[ATTR_ERROR]),
                        )

            except Exception:
                _LOGGER.exception("set_system_variable: Exception")
        else:
            try:
                return await self.proxy.setSystemVariable(name, value)
            except Exception:
                _LOGGER.exception("set_system_variable: Exception")

    async def get_service_messages(self):
        """Get service messages from CCU / Homegear."""
        try:
            return await self.proxy.getServiceMessages()
        except Exception:
            _LOGGER.exception("get_service_messages: Exception")

    async def rssi_info(self):
        """Get RSSI information for all devices from CCU / Homegear."""
        try:
            return await self.proxy.rssiInfo()
        except Exception:
            _LOGGER.exception("rssi_info: Exception")

    # pylint: disable=invalid-name
    async def set_install_mode(self, on=True, t=60, mode=1, address=None) -> None:
        """Activate or deactivate installmode on CCU / Homegear."""
        try:
            args = [on]
            if on and t:
                args.append(t)
                if address:
                    args.append(address)
                else:
                    args.append(mode)

            return await self.proxy.setInstallMode(*args)
        except Exception:
            _LOGGER.exception("set_install_mode: Exception")

    async def get_install_mode(self):
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return await self.proxy.getInstallMode()
        except Exception:
            _LOGGER.exception("Exception: Exception")

    async def get_all_metadata(self, address):
        """Get all metadata of device."""
        try:
            return await self.proxy.getAllMetadata(address)
        except Exception:
            _LOGGER.exception("get_all_metadata: Exception")

    async def get_metadata(self, address, key):
        """Get metadata of device."""
        try:
            return await self.proxy.getMetadata(address, key)
        except Exception:
            _LOGGER.exception("get_metadata: Exception")

    async def set_metadata(self, address, key, value):
        """Set metadata of device."""
        try:
            return await self.proxy.setMetadata(address, key, value)
        except Exception:
            _LOGGER.exception(".set_metadata: Exception")

    async def delete_metadata(self, address, key):
        """Delete metadata of device."""
        try:
            return await self.proxy.deleteMetadata(address, key)
        except Exception:
            _LOGGER.exception("delete_metadata: Exception")

    async def list_bidcos_interfaces(self):
        """Return all available BidCos Interfaces."""
        try:
            return await self.proxy.listBidcosInterfaces()
        except Exception:
            _LOGGER.exception("list_bidcos_interfaces: Exception")

    async def ping(self):
        """Send ping to CCU to generate PONG event."""
        try:
            success = await self.proxy.ping(self.interface_id)
            if success:
                self.time_initialized = int(time.time())
                return True
        except Exception:
            _LOGGER.exception("ping: Exception")
        self.time_initialized = 0
        return False

    async def homegear_check_init(self):
        """Check if proxy is still initialized."""
        if self.backend != BACKEND_HOMEGEAR:
            return
        try:
            if await self.proxy.clientServerInitialized(self.interface_id):
                self.time_initialized = int(time.time())
                return True
        except Exception:
            _LOGGER.exception("homegear_check_init: Exception")
        _LOGGER.warning(
            "homegear_check_init: Setting initialized to 0 for %s", self.interface_id
        )
        self.time_initialized = 0
        return False

    async def is_connected(self):
        """
        Perform actions required for connectivity check.
        Return connectivity state.
        """

        if self.backend == BACKEND_CCU:
            await self.ping()
        elif self.backend == BACKEND_HOMEGEAR:
            await self.homegear_check_init()
        diff = int(time.time()) - self.time_initialized
        if diff < config.INIT_TIMEOUT:
            return True
        return False

    async def put_paramset(self, address, paramset, value, rx_mode=None):
        """Set paramsets manually."""
        try:
            if rx_mode is None:
                return await self.proxy.putParamset(address, paramset, value)
            return await self.proxy.putParamset(address, paramset, value, rx_mode)
        except Exception:
            _LOGGER.exception("put_paramset: Exception")

    async def fetch_paramset(self, address, paramset, update=False):
        """
        Fetch a specific paramset and add it to the known ones.
        """
        if self.interface_id not in self.server.paramsets_cache:
            self.server.paramsets_cache[self.interface_id] = {}
        if address not in self.server.paramsets_cache[self.interface_id]:
            self.server.paramsets_cache[self.interface_id][address] = {}
        if (
            not paramset in self.server.paramsets_cache[self.interface_id][address]
            or update
        ):
            _LOGGER.debug("Fetching paramset %s for %s", paramset, address)
            if not self.server.paramsets_cache[self.interface_id][address]:
                self.server.paramsets_cache[self.interface_id][address] = {}
            try:
                self.server.paramsets_cache[self.interface_id][address][
                    paramset
                ] = await self.proxy.getParamsetDescription(address, paramset)
            except Exception:
                _LOGGER.exception(
                    "Unable to get paramset %s for address %s.", paramset, address
                )
        await self.server.save_paramsets()

    async def fetch_paramsets(self, device_description, update=False):
        """
        Fetch paramsets for provided device description.
        """
        if self.interface_id not in self.server.paramsets_cache:
            self.server.paramsets_cache[self.interface_id] = {}
        address = device_description[ATTR_HM_ADDRESS]
        if address not in self.server.paramsets_cache[self.interface_id] or update:
            _LOGGER.debug("Fetching paramsets for %s", address)
            self.server.paramsets_cache[self.interface_id][address] = {}
            for paramset in RELEVANT_PARAMSETS:
                if paramset not in device_description[ATTR_HM_PARAMSETS]:
                    continue
                try:
                    self.server.paramsets_cache[self.interface_id][address][
                        paramset
                    ] = await self.proxy.getParamsetDescription(address, paramset)
                except Exception:
                    _LOGGER.exception(
                        "Unable to get paramset %s for address %s.", paramset, address
                    )
                    self.server.paramsets_cache[self.interface_id][address][
                        paramset
                    ] = {}

    async def fetch_all_paramsets(self, skip_existing=False):
        """
        Fetch all paramsets for provided interface id.
        """
        if self.interface_id not in self.server.devices_raw_dict:
            self.server.devices_raw_dict[self.interface_id] = {}
        if self.interface_id not in self.server.paramsets_cache:
            self.server.paramsets_cache[self.interface_id] = {}
        for address, dd in self.server.devices_raw_dict[self.interface_id].items():
            if (
                skip_existing
                and address in self.server.paramsets_cache[self.interface_id]
            ):
                continue
            await self.fetch_paramsets(dd)
        await self.server.save_paramsets()

    async def update_paramsets(self, address):
        """
        Update paramsets for provided address.
        """
        if self.interface_id not in self.server.devices_raw_dict:
            _LOGGER.error(
                "Interface ID missing in self.server.devices_raw_dict. Not updating paramsets for %s.",
                address,
            )
            return
        if address not in self.server.devices_raw_dict[self.interface_id]:
            _LOGGER.error(
                "Channel missing in self.server.devices_raw_dict[interface_id]. Not updating paramsets for %s.",
                address,
            )
            return
        await self.fetch_paramsets(
            self.server.devices_raw_dict[self.interface_id][address], update=True
        )
        await self.server.save_paramsets()

    async def fetch_names(self):
        """Get all names."""
        if self.backend == BACKEND_CCU:
            await self.fetch_names_json()
        elif self.backend == BACKEND_HOMEGEAR:
            await self.fetch_names_metadata()

    async def fetch_names_json(self):
        """
        Get all names via JSON-RPS and store in data.NAMES.
        """
        if not self.backend == BACKEND_CCU:
            _LOGGER.warning(
                "fetch_names_json: No CCU detected. Not fetching names via JSON-RPC."
            )
            return
        if not self.username:
            _LOGGER.warning(
                "fetch_names_json: No username set. Not fetching names via JSON-RPC."
            )
            return
        _LOGGER.debug("fetch_names_json: Fetching names via JSON-RPC.")
        try:
            await self.json_rpc_renew()
            if not self.session:
                _LOGGER.warning(
                    "fetch_names_json: Login failed. Not fetching names via JSON-RPC."
                )
                return

            params = {ATTR_SESSION_ID: self.session}
            response = await self.json_rpc_post(
                self.host,
                self.json_port,
                "Interface.listInterfaces",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )
            interface = False
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                for i in response[ATTR_RESULT]:
                    if i[ATTR_PORT] in [
                        self.port,
                        self.port + 30000,
                        self.port + 40000,
                    ]:
                        interface = i[ATTR_NAME]
                        break
            _LOGGER.debug("fetch_names_json: Got interface: %s", interface)
            if not interface:
                return

            params = {ATTR_SESSION_ID: self.session}
            response = await self.json_rpc_post(
                self.host,
                self.json_port,
                "Device.listAllDetail",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )

            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                _LOGGER.debug("fetch_names_json: Resolving devicenames")
                for device in response[ATTR_RESULT]:
                    if device[ATTR_INTERFACE] != interface:
                        continue
                    try:
                        self.server.names_cache[self.interface_id][
                            device[ATTR_ADDRESS]
                        ] = device[ATTR_NAME]
                        for channel in device.get(ATTR_CHANNELS, []):
                            self.server.names_cache[self.interface_id][
                                channel[ATTR_ADDRESS]
                            ] = channel[ATTR_NAME]
                    except Exception:
                        _LOGGER.exception("fetch_names_json: Exception")

        except Exception:
            _LOGGER.exception("fetch_names_json: General exception")

    async def fetch_names_metadata(self):
        """
        Get all names from metadata (Homegear).
        """
        if not self.backend == BACKEND_HOMEGEAR:
            _LOGGER.warning(
                "fetch_names_metadata: No Homegear detected. Not fetching names via Metadata."
            )
            return
        _LOGGER.debug("fetch_names_metadata: Fetching names via Metadata.")
        for address in self.server.devices_raw_dict[self.interface_id]:
            try:
                self.server.names_cache[self.interface_id][
                    address
                ] = await self.proxy.getMetadata(address, ATTR_HM_NAME)
            except Exception:
                _LOGGER.exception("Failed to fetch name for device %s.", address)
