# pylint: disable=line-too-long,broad-except,inconsistent-return-statements
"""
The client-object and its methods.
"""

import logging
import socket
import time

from hahomematic import config, data
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
    DEFAULT_JSONPORT,
    DEFAULT_LOCAL_PORT,
    DEFAULT_NAME,
    DEFAULT_PASSWORD,
    DEFAULT_PATH,
    DEFAULT_TLS,
    DEFAULT_USER,
    DEFAULT_VERIFY_TLS,
    LOCALHOST,
    PORT_RFD,
    PROXY_INIT_FAILED,
    PROXY_INIT_SKIPPED,
    PROXY_INIT_SUCCESS,
    RELEVANT_PARAMSETS,
)
from hahomematic.helpers import build_api_url, json_rpc_post, parse_ccu_sys_var
from hahomematic.proxy import LockingServerProxy
from hahomematic.server import save_paramsets

LOG = logging.getLogger(__name__)


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
        username=DEFAULT_USER,
        password=DEFAULT_PASSWORD,
        tls=DEFAULT_TLS,
        verify_tls=DEFAULT_VERIFY_TLS,
        # connect -> do init
        connect=DEFAULT_CONNECT,
        callback_hostname=None,
        callback_port=None,
        json_port=DEFAULT_JSONPORT,
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
        self.id = f"{server.instance_name}-{name}"
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
            LOG.warning("Can't resolve host for %s: %s", self.name, self.host)
            raise ClientException(err) from err
        tmpsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        tmpsocket.settimeout(config.TIMEOUT)
        tmpsocket.connect((self.host, self.port))
        self.local_ip = tmpsocket.getsockname()[0]
        tmpsocket.close()
        LOG.debug("Got local ip: %s", self.local_ip)

        # Get callback address
        if callback_hostname is not None:
            self.callback_hostname = callback_hostname
        else:
            self.callback_hostname = self.local_ip
        if callback_port is not None:
            self.callback_port = int(callback_port)
        else:
            self.callback_port = self.server.local_port
        self.init_url = f"http://{self.callback_hostname}:{self.callback_port}"
        self.api_url = build_api_url(
            self.host,
            self.port,
            self.path,
            username=self.username,
            password=self.password,
            tls=self.tls,
        )
        self.proxy = LockingServerProxy(
            self.api_url, tls=self.tls, verify_tls=self.verify_tls
        )
        self.initialized = 0
        try:
            self.version = self.proxy.getVersion()
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
        data.CLIENTS[self.id] = self
        if self.init_url not in data.CLIENTS_BY_INIT_URL:
            data.CLIENTS_BY_INIT_URL[self.init_url] = []
        data.CLIENTS_BY_INIT_URL[self.init_url].append(self)

    def proxy_init(self):
        """
        To receive events the proxy has to tell the CCU / Homegear
        where to send the events. For that we call the init-method.
        """
        if not self.connect:
            LOG.debug("proxy_init: Skipping init for %s", self.name)
            return PROXY_INIT_SKIPPED
        if self.server is None:
            LOG.warning("proxy_init: Local server missing for %s", self.name)
            self.initialized = 0
            return PROXY_INIT_FAILED
        try:
            LOG.debug("proxy_init: init('%s', '%s')", self.init_url, self.id)
            self.proxy.init(self.init_url, self.id)
            LOG.info("proxy_init: Proxy for %s initialized", self.name)
        # pylint: disable=broad-except
        except Exception:
            LOG.exception("proxy_init: Failed to initialize proxy for %s", self.name)
            self.initialized = 0
            return PROXY_INIT_FAILED
        self.initialized = int(time.time())
        return PROXY_INIT_SUCCESS

    def proxy_de_init(self):
        """
        De-init to stop CCU from sending events for this remote.
        """
        if self.session:
            self.json_rpc_logout()
        if not self.connect:
            LOG.debug("proxy_de_init: Skipping de-init for %s", self.name)
            return PROXY_INIT_SKIPPED
        if self.server is None:
            LOG.warning("proxy_de_init: Local server missing for %s", self.name)
            return PROXY_INIT_FAILED
        if not self.initialized:
            LOG.debug(
                "proxy_de_init: Skipping de-init for %s (not initialized)", self.name
            )
            return PROXY_INIT_SKIPPED
        try:
            LOG.debug("proxy_de_init: init('%s')", self.init_url)
            self.proxy.init(self.init_url)
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "proxy_de_init: Failed to de-initialize proxy for %s", self.name
            )
            return PROXY_INIT_FAILED
        # TODO: Should the de-init really be skipped for other clients?
        #  for client in data.CLIENTS_BY_INIT_URL.get(self.init_url, []):
        #     LOG.debug("proxy_de_init: Setting client %s initialized status to False.", client.id)
        #     client.initialized = False
        self.initialized = 0
        return PROXY_INIT_SUCCESS

    def json_rpc_login(self):
        """Login to CCU and return session."""
        self.session = False
        try:
            params = {
                ATTR_USERNAME: self.username,
                ATTR_PASSWORD: self.password,
            }
            response = json_rpc_post(
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
                LOG.warning(
                    "json_rpc_login: Unable to open session: %s", response[ATTR_ERROR]
                )
        # pylint: disable=broad-except
        except Exception:
            LOG.exception("json_rpc_login: Exception while logging in via JSON-RPC")

    def json_rpc_renew(self):
        """Renew JSON-RPC session or perform login."""
        if not self.session:
            self.json_rpc_login()
            return

        try:
            response = json_rpc_post(
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
            self.json_rpc_login()
        except Exception:
            LOG.exception("json_rpc_renew: Exception while renewing JSON-RPC session.")

    def json_rpc_logout(self):
        """Logout of CCU."""
        if not self.session:
            LOG.warning("json_rpc_logout: Not logged in. Not logging out.")
            return
        try:
            params = {"_session_id_": self.session}
            response = json_rpc_post(
                self.host,
                self.json_port,
                "Session.logout",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )
            if response[ATTR_ERROR]:
                LOG.warning("json_rpc_logout: Logout error: %s", response[ATTR_RESULT])
        # pylint: disable=broad-except
        except Exception:
            LOG.exception("json_rpc_logout: Exception while logging in via JSON-RPC")
        return

    def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        variables = {}
        if self.backend == BACKEND_CCU and self.username and self.password:
            LOG.debug(
                "get_all_system_variables: Getting all System variables via JSON-RPC"
            )
            self.json_rpc_renew()
            if not self.session:
                return variables
            try:
                params = {"_session_id_": self.session}
                response = json_rpc_post(
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
                LOG.exception("get_all_system_variables: Exception")
        else:
            try:
                variables = self.proxy.getAllSystemVariables()
            except Exception:
                LOG.exception("get_all_system_variables: Exception")
        return variables

    def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        var = None
        if self.backend == BACKEND_CCU and self.username and self.password:
            LOG.debug("get_system_variable: Getting System variable via JSON-RPC")
            self.json_rpc_renew()
            if not self.session:
                return var
            try:
                params = {"_session_id_": self.session, ATTR_NAME: name}
                response = json_rpc_post(
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
                LOG.exception("get_system_variable: Exception")
        else:
            try:
                var = self.proxy.getSystemVariable(name)
            except Exception:
                LOG.exception("get_system_variable: Exception")
        return var

    def delete_system_variable(self, name):
        """Delete a system variable from CCU / Homegear."""
        if self.backend == BACKEND_CCU and self.username and self.password:
            LOG.debug("delete_system_variable: Getting System variable via JSON-RPC")
            self.json_rpc_renew()
            if not self.session:
                return
            try:
                params = {"_session_id_": self.session, ATTR_NAME: name}
                response = json_rpc_post(
                    self.host,
                    self.json_port,
                    "SysVar.deleteSysVarByName",
                    params,
                    tls=self.json_tls,
                    verify_tls=self.verify_tls,
                )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    deleted = response[ATTR_RESULT]
                    LOG.warning("delete_system_variable: Deleted: %s", str(deleted))

            except Exception:
                LOG.exception("delete_system_variable: Exception")
        else:
            try:
                return self.proxy.deleteSystemVariable(name)
            except Exception:
                LOG.exception("delete_system_variable: Exception")

    def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        if self.backend == BACKEND_CCU and self.username and self.password:
            LOG.debug("set_system_variable: Setting System variable via JSON-RPC")
            self.json_rpc_renew()
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
                    response = json_rpc_post(
                        self.host, self.json_port, "SysVar.setBool", params
                    )
                else:
                    response = json_rpc_post(
                        self.host, self.json_port, "SysVar.setFloat", params
                    )
                if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                    res = response[ATTR_RESULT]
                    LOG.debug(
                        "set_system_variable: Result while setting variable: %s",
                        str(res),
                    )
                else:
                    if response[ATTR_ERROR]:
                        LOG.debug(
                            "set_system_variable: Error while setting variable: %s",
                            str(response[ATTR_ERROR]),
                        )

            except Exception:
                LOG.exception("set_system_variable: Exception")
        else:
            try:
                return self.proxy.setSystemVariable(name, value)
            except Exception:
                LOG.exception("set_system_variable: Exception")

    def get_service_messages(self):
        """Get service messages from CCU / Homegear."""
        try:
            return self.proxy.getServiceMessages()
        except Exception:
            LOG.exception("get_service_messages: Exception")

    def rssi_info(self):
        """Get RSSI information for all devices from CCU / Homegear."""
        try:
            return self.proxy.rssiInfo()
        except Exception:
            LOG.exception("rssi_info: Exception")

    # pylint: disable=invalid-name
    def set_install_mode(self, on=True, t=60, mode=1, address=None):
        """Activate or deactivate installmode on CCU / Homegear."""
        try:
            args = [on]
            if on and t:
                args.append(t)
                if address:
                    args.append(address)
                else:
                    args.append(mode)

            return self.proxy.setInstallMode(*args)
        except Exception:
            LOG.exceptoin("set_install_mode: Exception")

    def get_install_mode(self):
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return self.proxy.getInstallMode()
        except Exception:
            LOG.exception("Exception: Exception")

    def get_all_metadata(self, address):
        """Get all metadata of device."""
        try:
            return self.proxy.getAllMetadata(address)
        except Exception:
            LOG.exception("get_all_metadata: Exception")

    def get_metadata(self, address, key):
        """Get metadata of device."""
        try:
            return self.proxy.getMetadata(address, key)
        except Exception:
            LOG.exception("get_metadata: Exception")

    def set_metadata(self, address, key, value):
        """Set metadata of device."""
        try:
            return self.proxy.setMetadata(address, key, value)
        except Exception:
            LOG.exception(".set_metadata: Exception")

    def delete_metadata(self, address, key):
        """Delete metadata of device."""
        try:
            return self.proxy.deleteMetadata(address, key)
        except Exception:
            LOG.exception("delete_metadata: Exception")

    def list_bidcos_interfaces(self):
        """Return all available BidCos Interfaces."""
        try:
            return self.proxy.listBidcosInterfaces()
        except Exception:
            LOG.exception("list_bidcos_interfaces: Exception")

    def ping(self):
        """Send ping to CCU to generate PONG event."""
        try:
            self.proxy.ping(self.id)
        except Exception:
            LOG.exception("ping: Exception")

    def homegear_check_init(self):
        """Check if proxy is still initialized."""
        if self.backend != BACKEND_HOMEGEAR:
            return
        try:
            if self.proxy.clientServerInitialized(self.id):
                self.initialized = int(time.time())
                return
        except Exception:
            LOG.exception("homegear_check_init: Exception")
        LOG.warning("homegear_check_init: Setting initialized to 0 for %s", self.id)
        self.initialized = 0

    def is_connected(self):
        """
        Perform actions required for connectivity check.
        Return connectivity state.
        """
        if self.backend == BACKEND_CCU:
            self.ping()
        elif self.backend == BACKEND_HOMEGEAR:
            self.homegear_check_init()
        diff = int(time.time()) - self.initialized
        if diff < config.INIT_TIMEOUT:
            return True
        return False

    def put_paramset(self, address, paramset, value, rx_mode=None):
        """Set paramsets manually."""
        try:
            if rx_mode is None:
                return self.proxy.putParamset(address, paramset, value)
            return self.proxy.putParamset(address, paramset, value, rx_mode)
        except Exception:
            LOG.exception("put_paramset: Exception")

    def fetch_paramset(self, address, paramset, update=False):
        """
        Fetch a specific paramset and add it to the known ones.
        """
        if self.id not in data.PARAMSETS:
            data.PARAMSETS[self.id] = {}
        if address not in data.PARAMSETS[self.id]:
            data.PARAMSETS[self.id][address] = {}
        if not paramset in data.PARAMSETS[self.id][address] or update:
            LOG.debug("Fetching paramset %s for %s", paramset, address)
            if not data.PARAMSETS[self.id][address]:
                data.PARAMSETS[self.id][address] = {}
            try:
                data.PARAMSETS[self.id][address][
                    paramset
                ] = self.proxy.getParamsetDescription(address, paramset)
            except Exception:
                LOG.exception(
                    "Unable to get paramset %s for address %s.", paramset, address
                )
        save_paramsets()

    def fetch_paramsets(self, device_description, update=False):
        """
        Fetch paramsets for provided device description.
        """
        if self.id not in data.PARAMSETS:
            data.PARAMSETS[self.id] = {}
        address = device_description[ATTR_HM_ADDRESS]
        if address not in data.PARAMSETS[self.id] or update:
            LOG.debug("Fetching paramsets for %s", address)
            data.PARAMSETS[self.id][address] = {}
            for paramset in RELEVANT_PARAMSETS:
                if paramset not in device_description[ATTR_HM_PARAMSETS]:
                    continue
                try:
                    data.PARAMSETS[self.id][address][
                        paramset
                    ] = self.proxy.getParamsetDescription(address, paramset)
                except Exception:
                    LOG.exception(
                        "Unable to get paramset %s for address %s.", paramset, address
                    )
                    data.PARAMSETS[self.id][address][paramset] = {}

    def fetch_all_paramsets(self, skip_existing=False):
        """
        Fetch all paramsets for provided interface id.
        """
        if self.id not in data.DEVICES_RAW_DICT:
            data.DEVICES_RAW_DICT[self.id] = {}
        if self.id not in data.PARAMSETS:
            data.PARAMSETS[self.id] = {}
        for address, dd in data.DEVICES_RAW_DICT[self.id].items():
            if skip_existing and address in data.PARAMSETS[self.id]:
                continue
            self.fetch_paramsets(dd)
        save_paramsets()

    def update_paramsets(self, address):
        """
        Update paramsets for provided address.
        """
        if self.id not in data.DEVICES_RAW_DICT:
            LOG.error(
                "Interface ID missing in data.DEVICES_RAW_DICT. Not updating paramsets for %s.",
                address,
            )
            return
        if not address in data.DEVICES_RAW_DICT[self.id]:
            LOG.error(
                "Channel missing in data.DEVICES_RAW_DICT[interface_id]. Not updating paramsets for %s.",
                address,
            )
            return
        self.fetch_paramsets(data.DEVICES_RAW_DICT[self.id][address], update=True)
        save_paramsets()

    def fetch_names_json(self):
        """
        Get all names via JSON-RPS and store in data.NAMES.
        """
        if not self.backend == BACKEND_CCU:
            LOG.warning(
                "fetch_names_json: No CCU detected. Not fetching names via JSON-RPC."
            )
            return
        if not self.username:
            LOG.warning(
                "fetch_names_json: No username set. Not fetching names via JSON-RPC."
            )
            return
        LOG.debug("fetch_names_json: Fetching names via JSON-RPC.")
        try:
            self.json_rpc_renew()
            if not self.session:
                LOG.warning(
                    "fetch_names_json: Login failed. Not fetching names via JSON-RPC."
                )
                return

            params = {ATTR_SESSION_ID: self.session}
            response = json_rpc_post(
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
            LOG.debug("fetch_names_json: Got interface: %s", interface)
            if not interface:
                return

            params = {ATTR_SESSION_ID: self.session}
            response = json_rpc_post(
                self.host,
                self.json_port,
                "Device.listAllDetail",
                params,
                tls=self.json_tls,
                verify_tls=self.verify_tls,
            )

            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                LOG.debug("fetch_names_json: Resolving devicenames")
                for device in response[ATTR_RESULT]:
                    if device[ATTR_INTERFACE] != interface:
                        continue
                    try:
                        data.NAMES[self.id][device[ATTR_ADDRESS]] = device[ATTR_NAME]
                        for channel in device.get(ATTR_CHANNELS, []):
                            data.NAMES[self.id][channel[ATTR_ADDRESS]] = channel[
                                ATTR_NAME
                            ]
                    except Exception:
                        LOG.exception("fetch_names_json: Exception")

        except Exception:
            LOG.exception("fetch_names_json: General exception")

    def fetch_names_metadata(self):
        """
        Get all names from metadata (Homegear).
        """
        if not self.backend == BACKEND_HOMEGEAR:
            LOG.warning(
                "fetch_names_metadata: No Homegear detected. Not fetching names via Metadata."
            )
            return
        LOG.debug("fetch_names_metadata: Fetching names via Metadata.")
        for address in data.DEVICES_RAW_DICT[self.id]:
            try:
                data.NAMES[self.id][address] = self.proxy.getMetadata(
                    address, ATTR_HM_NAME
                )
            except Exception:
                LOG.exception("Failed to fetch name for device %s.", address)
