"""The client-object and its methods."""
from abc import ABC, abstractmethod
from collections.abc import Awaitable
from concurrent.futures import ThreadPoolExecutor
import logging
import socket
import time
from typing import TypeVar

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
    ATTR_PORT,
    ATTR_RESULT,
    ATTR_VALUE,
    DEFAULT_CONNECT,
    DEFAULT_JSON_PORT,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PATH,
    DEFAULT_TLS,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_TLS,
    LOCALHOST,
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
from hahomematic.json_rpc import JsonRpcAioHttpSession
from hahomematic.proxy import ThreadPoolServerProxy

T = TypeVar("T")

_LOGGER = logging.getLogger(__name__)


class ClientException(Exception):
    """hahomematic Client exception."""


class Client(ABC):
    """
    Client object that initializes the XML-RPC proxy
    and provides access to other data via XML-RPC
    or JSON-RPC.
    """

    def __init__(self, client_config):
        """
        Initialize the Client.
        """
        self.server = client_config.server
        # Referred to as 'remote' in other places
        self.name = client_config.name
        # This is the actual interface_id used for init
        self.interface_id = f"{self.server.instance_name}-{self.name}"
        self.host = client_config.host
        self.port = client_config.port
        self.json_port = client_config.json_port
        self.connect = client_config.connect
        self.path = client_config.path
        self.password = client_config.password
        if self.password is None:
            self.username = None
        else:
            self.username = client_config.username
        self.tls = client_config.tls
        self.json_tls = client_config.json_tls
        self.verify_tls = client_config.verify_tls
        self.client_session = client_config.client_session
        try:
            socket.gethostbyname(self.host)
        except Exception as err:
            _LOGGER.warning("Can't resolve host for %s: %s", self.name, self.host)
            raise ClientException(err) from err
        tmp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tmp_socket.settimeout(config.TIMEOUT)
        tmp_socket.connect((self.host, self.port))
        self.local_ip = tmp_socket.getsockname()[0]
        tmp_socket.close()
        _LOGGER.debug("Got local ip: %s", self.local_ip)

        # Get callback address
        if client_config.callback_host is not None:
            self.callback_host = client_config.callback_host
        else:
            self.callback_host = self.local_ip
        if client_config.callback_port is not None:
            self.callback_port = int(client_config.callback_port)
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
        # for all device related interaction
        self._proxy_executor = ThreadPoolExecutor(
            max_workers=config.PROXY_EXECUTOR_MAX_WORKERS
        )
        self.proxy = ThreadPoolServerProxy(
            self.async_add_proxy_executor_job,
            self.api_url,
            tls=self.tls,
            verify_tls=self.verify_tls,
        )
        self.time_initialized = 0
        self.json_rpc_session = JsonRpcAioHttpSession(client=self)

        self.server.clients[self.interface_id] = self
        if self.init_url not in self.server.clients_by_init_url:
            self.server.clients_by_init_url[self.init_url] = []
        self.server.clients_by_init_url[self.init_url].append(self)

    async def proxy_init(self) -> int:
        """
        To receive events the proxy has to tell the CCU / Homegear
        where to send the events. For that we call the init-method.
        """
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
        if self.json_rpc_session.is_activated:
            await self.json_rpc_session.logout()
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
        except Exception:
            _LOGGER.exception(
                "proxy_de_init: Failed to de-initialize proxy for %s", self.name
            )
            return PROXY_DE_INIT_FAILED

        self.time_initialized = 0
        return PROXY_DE_INIT_SUCCESS

    async def proxy_re_init(self) -> int:
        """Reinit Proxy"""
        de_init_status = await self.proxy_de_init()
        if de_init_status is not PROXY_DE_INIT_FAILED:
            return await self.proxy_init()

    def stop(self):
        """Stop depending services."""
        self._proxy_executor.shutdown()

    async def async_add_proxy_executor_job(self, func, *args) -> Awaitable:
        """Add an executor job from within the event loop for all device related interaction."""
        return await self.server.loop.run_in_executor(self._proxy_executor, func, *args)

    @abstractmethod
    async def fetch_names(self):
        """Fetch names from backend."""
        ...

    async def is_connected(self):
        """
        Perform actions required for connectivity check.
        Return connectivity state.
        """
        await self._check_connection()

        diff = int(time.time()) - self.time_initialized
        if diff < config.INIT_TIMEOUT:
            return True
        return False

    @abstractmethod
    async def _check_connection(self):
        """Send ping to CCU to generate PONG event."""
        ...

    @abstractmethod
    async def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        ...

    @abstractmethod
    async def delete_system_variable(self, name):
        """Delete a system variable from CCU / Homegear."""
        ...

    @abstractmethod
    async def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        ...

    @abstractmethod
    async def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        ...

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
            paramset not in self.server.paramsets_cache[self.interface_id][address]
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
            _LOGGER.warning(
                "Interface ID missing in self.server.devices_raw_dict. Not updating paramsets for %s.",
                address,
            )
            return
        if address not in self.server.devices_raw_dict[self.interface_id]:
            _LOGGER.warning(
                "Channel missing in self.server.devices_raw_dict[_interface_id]. Not updating paramsets for %s.",
                address,
            )
            return
        await self.fetch_paramsets(
            self.server.devices_raw_dict[self.interface_id][address], update=True
        )
        await self.server.save_paramsets()


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    async def fetch_names(self):
        """
        Get all names via JSON-RPS and store in data.NAMES.
        """
        if not self.username:
            _LOGGER.warning(
                "fetch_names_json: No username set. Not fetching names via JSON-RPC."
            )
            return
        _LOGGER.debug("fetch_names_json: Fetching names via JSON-RPC.")
        try:
            if not await self.json_rpc_session.login_or_renew():
                _LOGGER.warning(
                    "fetch_names_json: Login failed. Not fetching names via JSON-RPC."
                )
                return

            response = await self.json_rpc_session.post(
                "Interface.listInterfaces",
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

            response = await self.json_rpc_session.post(
                "Device.listAllDetail",
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

    async def _check_connection(self):
        """Check if _proxy is still initialized."""
        try:
            success = await self.proxy.ping(self.interface_id)
            if success:
                self.time_initialized = int(time.time())
                return True
        except Exception:
            _LOGGER.exception("ping: Exception")
        self.time_initialized = 0
        return False

    async def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        if self.username and self.password:
            _LOGGER.debug("set_system_variable: Setting System variable via JSON-RPC")
            if not await self.json_rpc_session.login_or_renew():
                return
            try:
                params = {
                    ATTR_NAME: name,
                    ATTR_VALUE: value,
                }
                if value is True or value is False:
                    params[ATTR_VALUE] = int(value)
                    response = await self.json_rpc_session.post(
                        "SysVar.setBool", params
                    )
                else:
                    response = await self.json_rpc_session.post(
                        "SysVar.setFloat", params
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

    async def delete_system_variable(self, name):
        """Delete a system variable from CCU / Homegear."""
        if self.username and self.password:
            _LOGGER.debug(
                "delete_system_variable: Getting System variable via JSON-RPC"
            )
            if not await self.json_rpc_session.login_or_renew():
                return
            try:
                params = {ATTR_NAME: name}
                response = await self.json_rpc_session.post(
                    "SysVar.deleteSysVarByName",
                    params,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    deleted = response[ATTR_RESULT]
                    _LOGGER.info("delete_system_variable: Deleted: %s", str(deleted))
            except Exception:
                _LOGGER.exception("delete_system_variable: Exception")
        else:
            try:
                return await self.proxy.deleteSystemVariable(name)
            except Exception:
                _LOGGER.exception("delete_system_variable: Exception")

    async def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        var = None
        if self.username and self.password:
            _LOGGER.debug("get_system_variable: Getting System variable via JSON-RPC")
            if not await self.json_rpc_session.login_or_renew():
                return var
            try:
                params = {ATTR_NAME: name}
                response = await self.json_rpc_session.post(
                    "SysVar.getValueByName",
                    params,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    # This does not yet support strings
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

    async def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        variables = {}
        if self.username and self.password:
            _LOGGER.debug(
                "get_all_system_variables: Getting all System variables via JSON-RPC"
            )
            if not await self.json_rpc_session.login_or_renew():
                return variables
            try:
                response = await self.json_rpc_session.post(
                    "SysVar.getAll",
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


class ClientHomegear(Client):
    """Client implementation for Homegear backend."""

    async def fetch_names(self):
        """
        Get all names from metadata (Homegear).
        """
        _LOGGER.debug("fetch_names_metadata: Fetching names via Metadata.")
        for address in self.server.devices_raw_dict[self.interface_id]:
            try:
                self.server.names_cache[self.interface_id][
                    address
                ] = await self.proxy.getMetadata(address, ATTR_HM_NAME)
            except Exception:
                _LOGGER.exception("Failed to fetch name for device %s.", address)

    async def _check_connection(self):
        """Check if proxy is still initialized."""
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

    async def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        try:
            return await self.proxy.setSystemVariable(name, value)
        except Exception:
            _LOGGER.exception("set_system_variable: Exception")

    async def delete_system_variable(self, name):
        """Delete a system variable from CCU / Homegear."""
        try:
            return await self.proxy.deleteSystemVariable(name)
        except Exception:
            _LOGGER.exception("delete_system_variable: Exception")

    async def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        try:
            return await self.proxy.getSystemVariable(name)
        except Exception:
            _LOGGER.exception("get_system_variable: Exception")

    async def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        try:
            return await self.proxy.getAllSystemVariables()
        except Exception:
            _LOGGER.exception("get_all_system_variables: Exception")


class ClientFactory:
    """Config for a Client."""

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
        client_session=None,
        connect=DEFAULT_CONNECT,
        callback_host=None,
        callback_port=None,
        json_port=DEFAULT_JSON_PORT,
        json_tls=DEFAULT_TLS,
    ):
        self.server = server
        self.name = name
        self.host = host
        self.port: int = port
        self.path = path
        self.username = username
        self.password = password
        self.tls = tls
        self.verify_tls = verify_tls
        self.client_session = client_session
        self.connect = connect
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.json_port = json_port
        self.json_tls = json_tls

    async def get_client(self) -> Client:
        """Identify the used client."""

        api_url = build_api_url(
            host=self.host,
            port=self.port,
            path=self.path,
            username=self.username,
            password=self.password,
            tls=self.tls,
        )

        proxy = ThreadPoolServerProxy(
            self.server.async_add_executor_job,
            api_url,
            tls=self.tls,
            verify_tls=self.verify_tls,
        )
        try:
            version = await proxy.getVersion()
        except Exception as err:
            raise Exception(
                f"Failed to get backend version. Not creating client: {api_url}"
            ) from err
        if "Homegear" in version or "pydevccu" in version:
            return ClientHomegear(self)
        return ClientCCU(self)
