"""The client-object and its methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
import logging
from typing import Any

from hahomematic import config
import hahomematic.central_unit as hm_central
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CHANNELS,
    ATTR_ERROR,
    ATTR_HM_ADDRESS,
    ATTR_HM_NAME,
    ATTR_HM_PARAMSETS,
    ATTR_NAME,
    ATTR_RESULT,
    ATTR_VALUE,
    BACKEND_CCU,
    BACKEND_HOMEGEAR,
    BACKEND_PYDEVCCU,
    HM_VIRTUAL_REMOTES,
    INIT_DATETIME,
    PROXY_DE_INIT_FAILED,
    PROXY_DE_INIT_SKIPPED,
    PROXY_DE_INIT_SUCCESS,
    PROXY_INIT_FAILED,
    PROXY_INIT_SUCCESS,
    RELEVANT_PARAMSETS,
)
from hahomematic.device import HmDevice
from hahomematic.exceptions import NoConnection, ProxyException
from hahomematic.helpers import build_api_url, get_local_ip, parse_ccu_sys_var
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.xml_rpc_proxy import XmlRpcProxy

_LOGGER = logging.getLogger(__name__)


class Client(ABC):
    """
    Client object that initializes the XML-RPC proxy
    and provides access to other data via XML-RPC
    or JSON-RPC.
    """

    def __init__(self, client_config: ClientConfig):
        """
        Initialize the Client.
        """
        self._client_config: ClientConfig = client_config
        self._central: hm_central.CentralUnit = self._client_config.central
        self._version: str | None = self._client_config.version
        self.name: str = self._client_config.name
        # This is the actual interface_id used for init
        self.interface_id: str = f"{self._central.instance_name}-{self.name}"
        self._has_credentials = self._client_config.has_credentials
        self._init_url: str = self._client_config.init_url
        # for all device related interaction
        self._proxy: XmlRpcProxy = self._client_config.xml_rpc_proxy
        self.last_updated: datetime = INIT_DATETIME
        self._json_rpc_session: JsonRpcAioHttpClient = self._central.json_rpc_session

    @property
    def version(self) -> str | None:
        """Return the version of the backend."""
        return self._version

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return ""

    @property
    def central(self) -> hm_central.CentralUnit:
        """Return the central of the backend."""
        return self._central

    @property
    def init_url(self) -> str:
        """Return the init_url of the client."""
        return self._init_url

    async def proxy_init(self) -> int:
        """
        To receive events the proxy has to tell the CCU / Homegear
        where to send the events. For that we call the init-method.
        """
        try:
            _LOGGER.debug(
                "proxy_init: init('%s', '%s')", self._init_url, self.interface_id
            )
            await self._proxy.init(self._init_url, self.interface_id)
            _LOGGER.info("proxy_init: Proxy for %s initialized", self.interface_id)
        except ProxyException:
            _LOGGER.exception(
                "proxy_init: Failed to initialize proxy for %s", self.interface_id
            )
            self.last_updated = INIT_DATETIME
            return PROXY_INIT_FAILED
        self.last_updated = datetime.now()
        return PROXY_INIT_SUCCESS

    async def proxy_de_init(self) -> int:
        """
        De-init to stop CCU from sending events for this remote.
        """
        if self._json_rpc_session.is_activated:
            await self._json_rpc_session.logout()
        if self.last_updated == INIT_DATETIME:
            _LOGGER.debug(
                "proxy_de_init: Skipping de-init for %s (not initialized)", self.name
            )
            return PROXY_DE_INIT_SKIPPED
        try:
            _LOGGER.debug("proxy_de_init: init('%s')", self._init_url)
            await self._proxy.init(self._init_url)
        except ProxyException:
            _LOGGER.exception(
                "proxy_de_init: Failed to de-initialize proxy for %s", self.name
            )
            return PROXY_DE_INIT_FAILED

        self.last_updated = INIT_DATETIME
        return PROXY_DE_INIT_SUCCESS

    async def proxy_re_init(self) -> int:
        """Reinit Proxy"""
        de_init_status = await self.proxy_de_init()
        if de_init_status is not PROXY_DE_INIT_FAILED:
            return await self.proxy_init()
        return PROXY_DE_INIT_FAILED

    def stop(self) -> None:
        """Stop depending services."""
        self._proxy.stop()

    @abstractmethod
    async def fetch_names(self) -> None:
        """Fetch names from backend."""
        ...

    async def is_connected(self) -> bool:
        """
        Perform actions required for connectivity check.
        Return connectivity state.
        """
        is_connected = await self._check_connection()
        if not is_connected:
            return False

        diff: timedelta = datetime.now() - self.last_updated
        if diff.total_seconds() < config.INIT_TIMEOUT:
            return True
        return False

    @abstractmethod
    async def _check_connection(self) -> bool:
        """Send ping to CCU to generate PONG event."""
        ...

    @abstractmethod
    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        ...

    @abstractmethod
    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        ...

    @abstractmethod
    async def get_system_variable(self, name: str) -> str:
        """Get single system variable from CCU / Homegear."""
        ...

    @abstractmethod
    async def get_all_system_variables(self) -> dict[str, Any]:
        """Get all system variables from CCU / Homegear."""
        ...

    @abstractmethod
    async def get_all_rooms(self) -> dict[str, str]:
        """Get all rooms, if available."""
        ...

    @abstractmethod
    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        ...

    async def get_service_messages(self) -> Any:
        """Get service messages from CCU / Homegear."""
        try:
            return await self._proxy.getServiceMessages()
        except ProxyException:
            _LOGGER.exception("get_service_messages: ProxyException")
        return None

    # pylint: disable=invalid-name
    async def set_install_mode(
        self,
        on: bool = True,
        t: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> None:
        """Activate or deactivate installmode on CCU / Homegear."""
        try:
            args: list[Any] = [on]
            if on and t:
                args.append(t)
                if device_address:
                    args.append(device_address)
                else:
                    args.append(mode)

            await self._proxy.setInstallMode(*args)
        except ProxyException:
            _LOGGER.exception("set_install_mode: ProxyException")

    async def get_install_mode(self) -> Any:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return await self._proxy.getInstallMode()
        except ProxyException:
            _LOGGER.exception("get_install_mode: ProxyException")
        return 0

    async def get_value(self, channel_address: str, parameter: str) -> Any:
        """Return a value from CCU."""
        try:
            return await self._proxy.getValue(channel_address, parameter)
        except ProxyException as pex:
            # _LOGGER.debug("get_value: ProxyException")
            raise ProxyException from pex

    async def set_value(
        self,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set single value on paramset VALUES."""
        try:
            if rx_mode:
                await self._proxy.setValue(channel_address, parameter, value, rx_mode)
            else:
                await self._proxy.setValue(channel_address, parameter, value)
        except ProxyException:
            _LOGGER.exception("set_value: ProxyException")

    async def put_paramset(
        self,
        channel_address: str,
        paramset: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set paramsets manually."""
        try:
            if rx_mode:
                await self._proxy.putParamset(channel_address, paramset, value, rx_mode)
            else:
                await self._proxy.putParamset(channel_address, paramset, value)

        except ProxyException:
            _LOGGER.exception("put_paramset: ProxyException")

    async def fetch_paramset(self, channel_address: str, paramset: str) -> None:
        """
        Fetch a specific paramset and add it to the known ones.
        """
        _LOGGER.debug("Fetching paramset %s for %s", paramset, channel_address)

        try:
            parameter_data = await self._proxy.getParamsetDescription(
                channel_address, paramset
            )
            self._central.paramsets.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset=paramset,
                paramset_description=parameter_data,
            )
        except ProxyException:
            _LOGGER.exception(
                "Unable to get paramset %s for channel_address %s.",
                paramset,
                channel_address,
            )
        await self._central.paramsets.save()

    async def fetch_paramsets(
        self, device_description: dict[str, Any], update: bool = False
    ) -> None:
        """
        Fetch paramsets for provided device description.
        """
        data = await self.get_paramsets(
            device_description=device_description, relevant_paramsets=RELEVANT_PARAMSETS
        )
        for address, paramsets in data.items():
            _LOGGER.debug("Fetching paramsets for %s", address)
            for paramset, paramset_description in paramsets.items():
                self._central.paramsets.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset=paramset,
                    paramset_description=paramset_description,
                )

    async def get_paramsets(
        self,
        device_description: dict[str, Any],
        relevant_paramsets: list[str] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Get paramsets for provided device description."""
        if not device_description:
            return {}
        paramsets: dict[str, dict[str, Any]] = {}
        address = device_description[ATTR_HM_ADDRESS]
        paramsets[address] = {}
        _LOGGER.debug("Fetching paramsets for %s", address)
        for paramset in device_description.get(ATTR_HM_PARAMSETS, []):
            if relevant_paramsets and paramset not in relevant_paramsets:
                continue
            try:
                paramsets[address][paramset] = await self._proxy.getParamsetDescription(
                    address, paramset
                )
            except ProxyException:
                _LOGGER.exception(
                    "Unable to get paramset %s for address %s.", paramset, address
                )
        return paramsets

    async def get_all_paramsets(
        self, device_descriptions: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Get all paramsets for provided device descriptions."""
        all_paramsets: dict[str, dict[str, Any]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(
                await self.get_paramsets(device_description=device_description)
            )
        return all_paramsets

    async def update_paramsets(self, device_address: str) -> None:
        """
        Update paramsets for provided device_address.
        """
        if not self._central.raw_devices.get_interface(interface_id=self.interface_id):
            _LOGGER.warning(
                "Interface ID missing in central_unit.raw_devices.devices_raw_dict. Not updating paramsets for %s.",
                device_address,
            )
            return
        if not self._central.raw_devices.get_device(
            interface_id=self.interface_id, device_address=device_address
        ):
            _LOGGER.warning(
                "Channel missing in central_unit.raw_devices.devices_raw_dict[_interface_id]. Not updating paramsets for %s.",
                device_address,
            )
            return
        await self.fetch_paramsets(
            self._central.raw_devices.get_device(
                interface_id=self.interface_id, device_address=device_address
            ),
            update=True,
        )
        await self._central.paramsets.save()


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return BACKEND_CCU

    async def fetch_names(self) -> None:
        """
        Get all names via JSON-RPS and store in data.NAMES.
        """
        if not self._has_credentials:
            _LOGGER.warning(
                "fetch_names_json: No username set. Not fetching names via JSON-RPC."
            )
            return
        _LOGGER.debug("fetch_names_json: Fetching names via JSON-RPC.")
        try:
            response = await self._json_rpc_session.post(
                "Device.listAllDetail",
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                _LOGGER.debug("fetch_names_json: Resolving devicenames")
                for device in response[ATTR_RESULT]:
                    self._central.names.add(device[ATTR_ADDRESS], device[ATTR_NAME])
                    for channel in device.get(ATTR_CHANNELS, []):
                        self._central.names.add(
                            channel[ATTR_ADDRESS], channel[ATTR_NAME]
                        )
        except Exception:
            _LOGGER.exception("fetch_names_json: General exception")

    async def _check_connection(self) -> bool:
        """Check if _proxy is still initialized."""
        try:
            success = await self._proxy.ping(self.interface_id)
            if success:
                self.last_updated = datetime.now()
                return True
        except NoConnection:
            _LOGGER.exception("ping: NoConnection")
        except ProxyException:
            _LOGGER.exception("ping: ProxyException")
        self.last_updated = INIT_DATETIME
        return False

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        if not self._has_credentials:
            _LOGGER.warning(
                "set_system_variable: You have to set username ans password to set a system variable via JSON-RPC"
            )
            return
        _LOGGER.debug("set_system_variable: Setting System variable via JSON-RPC")
        try:
            params = {
                ATTR_NAME: name,
                ATTR_VALUE: value,
            }
            if value is True or value is False:
                params[ATTR_VALUE] = int(value)
                response = await self._json_rpc_session.post("SysVar.setBool", params)
            else:
                response = await self._json_rpc_session.post("SysVar.setFloat", params)
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

    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        if not self._has_credentials:
            _LOGGER.warning(
                "delete_system_variable: You have to set username ans password to delete a system variable via JSON-RPC"
            )
            return

        _LOGGER.debug("delete_system_variable: Getting System variable via JSON-RPC")
        try:
            params = {ATTR_NAME: name}
            response = await self._json_rpc_session.post(
                "SysVar.deleteSysVarByName",
                params,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                deleted = response[ATTR_RESULT]
                _LOGGER.info("delete_system_variable: Deleted: %s", str(deleted))
        except Exception:
            _LOGGER.exception("delete_system_variable: Exception")

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        var = None
        if not self._has_credentials:
            _LOGGER.warning(
                "get_system_variable: You have to set username ans password to get a system variable via JSON-RPC"
            )
            return var

        _LOGGER.debug("get_system_variable: Getting System variable via JSON-RPC")
        try:
            params = {ATTR_NAME: name}
            response = await self._json_rpc_session.post(
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

        return var

    async def get_all_system_variables(self) -> dict[str, Any]:
        """Get all system variables from CCU / Homegear."""
        variables: dict[str, Any] = {}
        if not self._has_credentials:
            _LOGGER.warning(
                "get_all_system_variables: You have to set username ans password to get system variables via JSON-RPC"
            )
            return variables

        _LOGGER.debug(
            "get_all_system_variables: Getting all system variables via JSON-RPC"
        )
        try:
            response = await self._json_rpc_session.post(
                "SysVar.getAll",
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                for var in response[ATTR_RESULT]:
                    key, value = parse_ccu_sys_var(var)
                    variables[key] = value
        except Exception:
            _LOGGER.exception("get_all_system_variables: Exception")

        return variables

    async def get_all_rooms(self) -> dict[str, str]:
        """Get all rooms from CCU."""
        rooms: dict[str, str] = {}
        device_channel_ids = await self._get_device_channel_ids()
        channel_ids_room = await self._get_all_channel_ids_room()
        for address, channel_id in device_channel_ids.items():
            if name := channel_ids_room.get(channel_id):
                rooms[address] = name
        return rooms

    async def _get_all_channel_ids_room(self) -> dict[str, str]:
        """Get all channel_ids per room from CCU / Homegear."""
        channel_ids_room: dict[str, str] = {}
        if not self._has_credentials:
            _LOGGER.warning(
                "_get_all_channel_ids_per_room: You have to set username ans password to get rooms via JSON-RPC"
            )
            return channel_ids_room

        _LOGGER.debug("_get_all_channel_ids_per_room: Getting all rooms via JSON-RPC")
        try:
            response = await self._json_rpc_session.post(
                "Room.getAll",
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                for room in response[ATTR_RESULT]:
                    channel_ids_room[room["id"]] = room["name"]
                    for channel_id in room["channelIds"]:
                        channel_ids_room[channel_id] = room["name"]
        except Exception:
            _LOGGER.exception("_get_all_channel_ids_per_room: Exception")

        return channel_ids_room

    async def _get_device_channel_ids(self) -> dict[str, str]:
        """Get all device_channel_ids from CCU / Homegear."""
        device_channel_ids: dict[str, str] = {}
        if not self._has_credentials:
            _LOGGER.warning(
                "_get_device_channel_ids: You have to set username ans password to get device channel_ids via JSON-RPC"
            )
            return device_channel_ids

        _LOGGER.debug(
            "_get_all_device_details: Getting all device channel_ids via JSON-RPC"
        )
        try:
            response = await self._json_rpc_session.post(
                "Device.listAllDetail",
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                for device in response[ATTR_RESULT]:
                    device_channel_ids[device["address"]] = device["id"]
                    for channel in device["channels"]:
                        device_channel_ids[channel["address"]] = channel["id"]
        except Exception:
            _LOGGER.exception("_get_device_channel_ids: Exception")

        return device_channel_ids

    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for device_type in HM_VIRTUAL_REMOTES:
            for hm_device in self._central.hm_devices.values():
                if (
                    hm_device.interface_id == self.interface_id
                    and hm_device.device_type == device_type
                ):
                    return hm_device
        return None


class ClientHomegear(Client):
    """Client implementation for Homegear backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        if self.version:
            return (
                BACKEND_PYDEVCCU
                if BACKEND_PYDEVCCU.lower() in self.version
                else BACKEND_HOMEGEAR
            )
        return BACKEND_CCU

    async def fetch_names(self) -> None:
        """
        Get all names from metadata (Homegear).
        """
        _LOGGER.debug("fetch_names_metadata: Fetching names via Metadata.")
        for address in self._central.raw_devices.get_interface(
            interface_id=self.interface_id
        ):
            try:
                self._central.names.add(
                    address,
                    await self._proxy.getMetadata(address, ATTR_HM_NAME),
                )
            except ProxyException:
                _LOGGER.exception("Failed to fetch name for device %s.", address)

    async def _check_connection(self) -> bool:
        """Check if proxy is still initialized."""
        try:
            if await self._proxy.clientServerInitialized(self.interface_id):
                self.last_updated = datetime.now()
                return True
        except NoConnection:
            _LOGGER.exception("ping: NoConnection")
        except ProxyException:
            _LOGGER.exception("homegear_check_init: ProxyException")
        _LOGGER.warning(
            "homegear_check_init: Setting initialized to 0 for %s", self.interface_id
        )
        self.last_updated = INIT_DATETIME
        return False

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        try:
            await self._proxy.setSystemVariable(name, value)
        except ProxyException:
            _LOGGER.exception("set_system_variable: ProxyException")

    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        try:
            await self._proxy.deleteSystemVariable(name)
        except ProxyException:
            _LOGGER.exception("delete_system_variable: ProxyException")

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        try:
            return await self._proxy.getSystemVariable(name)
        except ProxyException:
            _LOGGER.exception("get_system_variable: ProxyException")

    async def get_all_system_variables(self) -> Any:
        """Get all system variables from CCU / Homegear."""
        try:
            return await self._proxy.getAllSystemVariables()
        except ProxyException:
            _LOGGER.exception("get_all_system_variables: ProxyException")
        return None

    async def get_all_rooms(self) -> dict[str, str]:
        """Get all rooms from Homegear."""
        return {}

    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        return None


class ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        central: hm_central.CentralUnit,
        name: str,
        port: int,
        path: str | None = None,
    ):
        self.central = central
        self.name = name
        self._central_config = self.central.central_config
        self._callback_host: str = (
            self._central_config.callback_host
            if self._central_config.callback_host
            else get_local_ip(host=self._central_config.host, port=port)
        )
        self._callback_port: int = (
            self._central_config.callback_port
            if self._central_config.callback_port
            else self.central.local_port
        )
        self.init_url: str = f"http://{self._callback_host}:{self._callback_port}"
        self.api_url = build_api_url(
            host=self._central_config.host,
            port=port,
            path=path,
            username=self._central_config.username,
            password=self._central_config.password,
            tls=self._central_config.tls,
        )
        self.has_credentials: bool = (
            self._central_config.username is not None
            and self._central_config.password is not None
        )
        self.version: str | None = None
        self.xml_rpc_proxy: XmlRpcProxy = XmlRpcProxy(
            self.central.loop,
            self.api_url,
            tls=self._central_config.tls,
            verify_tls=self._central_config.verify_tls,
        )

    async def get_client(self) -> Client:
        """Identify the used client."""
        try:
            self.version = await self.xml_rpc_proxy.getVersion()
        except ProxyException as err:
            raise ProxyException(
                f"Failed to get backend version. Not creating client: {self.api_url}"
            ) from err
        if self.version:
            if "Homegear" in self.version or "pydevccu" in self.version:
                return ClientHomegear(self)
        return ClientCCU(self)
