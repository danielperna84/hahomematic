"""The client-object and its methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic import central_unit as hmcu
from hahomematic.config import CALLBACK_WARN_INTERVAL, RECONNECT_WAIT
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_AVAILABLE,
    ATTR_CHANNELS,
    ATTR_ID,
    ATTR_INTERFACE,
    ATTR_NAME,
    ATTR_SECONDS_SINCE_LAST_EVENT,
    HM_VIRTUAL_REMOTE_TYPES,
    HOMEGEAR_SERIAL,
    IF_BIDCOS_RF_NAME,
    IF_NAMES,
    INIT_DATETIME,
    HmBackend,
    HmCallSource,
    HmDescription,
    HmForcedDeviceAvailability,
    HmInterface,
    HmInterfaceEventType,
    HmParamsetKey,
    HmProductGroup,
    HmProxyInitState,
)
from hahomematic.exceptions import AuthFailure, BaseHomematicException, NoConnection
from hahomematic.platforms.device import HmDevice
from hahomematic.support import (
    ProgramData,
    SystemInformation,
    SystemVariableData,
    build_headers,
    build_xml_rpc_uri,
    get_channel_no,
    measure_execution_time,
    reduce_args,
)
from hahomematic.xml_rpc_proxy import XmlRpcProxy

_LOGGER = logging.getLogger(__name__)


class Client(ABC):
    """Client object to access the backends via XML-RPC or JSON-RPC."""

    def __init__(self, client_config: _ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        self.central: Final[hmcu.CentralUnit] = client_config.central

        self._json_rpc_client: Final = client_config.central.json_rpc_client

        self.interface: Final = client_config.interface
        self.interface_id: Final = client_config.interface_id
        self.version: Final = client_config.version
        self._attr_available: bool = True
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self.last_updated: datetime = INIT_DATETIME

        self._proxy: XmlRpcProxy
        self._proxy_read: XmlRpcProxy
        self.system_information: SystemInformation

    async def init_client(self) -> None:
        """Init the client."""
        self.system_information = await self._get_system_information()
        self._proxy = self._config.get_xml_rpc_proxy(
            auth_enabled=self.system_information.auth_enabled
        )
        self._proxy_read = self._config.get_xml_rpc_proxy(
            auth_enabled=self.system_information.auth_enabled
        )

    @property
    def available(self) -> bool:
        """Return the availability of the client."""
        return self._attr_available

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model of the backend."""

    @property
    @abstractmethod
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""

    async def proxy_init(self) -> HmProxyInitState:
        """Init the proxy has to tell the CCU / Homegear where to send the events."""
        try:
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", self._config.init_url, self.interface_id)
            await self._proxy.init(self._config.init_url, self.interface_id)
            self._mark_all_devices_forced_availability(
                forced_availability=HmForcedDeviceAvailability.NOT_SET
            )
            _LOGGER.debug("PROXY_INIT: Proxy for %s initialized", self.interface_id)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                hhe.name,
                reduce_args(args=hhe.args),
                self.interface_id,
            )
            self.last_updated = INIT_DATETIME
            return HmProxyInitState.INIT_FAILED
        self.last_updated = datetime.now()
        return HmProxyInitState.INIT_SUCCESS

    async def proxy_de_init(self) -> HmProxyInitState:
        """De-init to stop CCU from sending events for this remote."""
        if self.last_updated == INIT_DATETIME:
            _LOGGER.debug(
                "PROXY_DE_INIT: Skipping de-init for %s (not initialized)",
                self.interface_id,
            )
            return HmProxyInitState.DE_INIT_SKIPPED
        try:
            _LOGGER.debug("PROXY_DE_INIT: init('%s')", self._config.init_url)
            await self._proxy.init(self._config.init_url)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "PROXY_DE_INIT failed: %s [%s] Unable to de-initialize proxy for %s",
                hhe.name,
                reduce_args(args=hhe.args),
                self.interface_id,
            )
            return HmProxyInitState.DE_INIT_FAILED

        self.last_updated = INIT_DATETIME
        return HmProxyInitState.DE_INIT_SUCCESS

    async def proxy_re_init(self) -> HmProxyInitState:
        """Reinit Proxy."""
        if await self.proxy_de_init() != HmProxyInitState.DE_INIT_FAILED:
            return await self.proxy_init()
        return HmProxyInitState.DE_INIT_FAILED

    def _mark_all_devices_forced_availability(
        self, forced_availability: HmForcedDeviceAvailability
    ) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != HmForcedDeviceAvailability.FORCE_FALSE
        if self._attr_available != available:
            for device in self.central.devices:
                if device.interface_id == self.interface_id:
                    device.set_forced_availability(forced_availability=forced_availability)
            self._attr_available = available
            _LOGGER.debug(
                "MARK_ALL_DEVICES_FORCED_AVAILABILITY: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )
        self.central.fire_interface_event(
            interface_id=self.interface_id,
            interface_event_type=HmInterfaceEventType.PROXY,
            data={ATTR_AVAILABLE: available},
        )

    async def reconnect(self) -> bool:
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.debug(
                "RECONNECT: waiting to re-connect client %s for %is",
                self.interface_id,
                int(RECONNECT_WAIT),
            )
            await asyncio.sleep(RECONNECT_WAIT)

            await self.proxy_re_init()
            _LOGGER.info(
                "RECONNECT: re-connected client %s",
                self.interface_id,
            )
            return True
        return False

    def stop(self) -> None:
        """Stop depending services."""
        self._proxy.stop()
        self._proxy_read.stop()

    @abstractmethod
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""

    @abstractmethod
    async def fetch_device_details(self) -> None:
        """Fetch names from backend."""

    async def is_connected(self) -> bool:
        """
        Perform actions required for connectivity check.

        Connection is not connected, if three consecutive checks fail.
        Return connectivity state.
        """
        if await self.check_connection_availability() is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        if self._connection_error_count > 3:
            self._mark_all_devices_forced_availability(
                forced_availability=HmForcedDeviceAvailability.FORCE_FALSE
            )
            return False

        if (datetime.now() - self.last_updated).total_seconds() < CALLBACK_WARN_INTERVAL:
            return True
        return False

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if last_events_time := self.central.last_events.get(self.interface_id):
            seconds_since_last_event = (datetime.now() - last_events_time).total_seconds()
            if seconds_since_last_event > CALLBACK_WARN_INTERVAL:
                if self._is_callback_alive:
                    self.central.fire_interface_event(
                        interface_id=self.interface_id,
                        interface_event_type=HmInterfaceEventType.CALLBACK,
                        data={
                            ATTR_AVAILABLE: False,
                            ATTR_SECONDS_SINCE_LAST_EVENT: int(seconds_since_last_event),
                        },
                    )
                    self._is_callback_alive = False
                _LOGGER.warning(
                    "IS_CALLBACK_ALIVE: Callback for %s has not received events for %is",
                    self.interface_id,
                    seconds_since_last_event,
                )
                return False

            if not self._is_callback_alive:
                self.central.fire_interface_event(
                    interface_id=self.interface_id,
                    interface_event_type=HmInterfaceEventType.CALLBACK,
                    data={ATTR_AVAILABLE: True},
                )
                self._is_callback_alive = True
        return True

    @abstractmethod
    async def check_connection_availability(self) -> bool:
        """Send ping to CCU to generate PONG event."""

    @abstractmethod
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear.."""

    @abstractmethod
    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""

    @abstractmethod
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""

    @abstractmethod
    async def get_system_variable(self, name: str) -> str:
        """Get single system variable from CCU / Homegear."""

    @abstractmethod
    async def get_all_system_variables(self, include_internal: bool) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""

    @abstractmethod
    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get all programs, if available."""

    @abstractmethod
    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms, if available."""

    @abstractmethod
    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions, if available."""

    @abstractmethod
    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""

    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for device_type in HM_VIRTUAL_REMOTE_TYPES:
            for device in self.central.devices:
                if device.interface_id == self.interface_id and device.device_type == device_type:
                    return device
        return None

    @measure_execution_time
    async def get_all_device_descriptions(self) -> Any:
        """Get device descriptions from CCU / Homegear."""
        try:
            return await self._proxy.listDevices()
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "GET_ALL_DEVICE_DESCRIPTIONS failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
        return None

    async def get_device_descriptions(self, device_address: str) -> Any:
        """Get device descriptions from CCU / Homegear."""
        try:
            if device_descriptions := await self._proxy_read.getDeviceDescription(device_address):
                return [device_descriptions]
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "GET_DEVICE_DESCRIPTIONS failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
        return None

    # pylint: disable=invalid-name
    async def set_install_mode(
        self,
        on: bool = True,
        t: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
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
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "SET_INSTALL_MODE failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
            return False
        return True

    async def get_install_mode(self) -> Any:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return await self._proxy.getInstallMode()
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "GET_INSTALL_MODE failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
        return 0

    async def get_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        call_source: HmCallSource = HmCallSource.MANUAL_OR_SCHEDULED,
    ) -> Any:
        """Return a value from CCU."""
        try:
            _LOGGER.debug(
                "GET_VALUE: channel_address %s, parameter %s, paramset_key, %s, source:%s",
                channel_address,
                parameter,
                paramset_key,
                call_source,
            )
            if paramset_key == HmParamsetKey.VALUES:
                return await self._proxy_read.getValue(channel_address, parameter)
            paramset = (
                await self._proxy_read.getParamset(channel_address, HmParamsetKey.MASTER) or {}
            )
            return paramset.get(parameter)
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "GET_VALUE failed with %s [%s]: %s, %s, %s",
                hhe.name,
                reduce_args(args=hhe.args),
                channel_address,
                parameter,
                paramset_key,
            )
            raise

    async def _set_value(
        self,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> bool:
        """Set single value on paramset VALUES."""
        try:
            _LOGGER.debug("SET_VALUE: %s, %s, %s", channel_address, parameter, value)
            if rx_mode:
                await self._proxy.setValue(channel_address, parameter, value, rx_mode)
            else:
                await self._proxy.setValue(channel_address, parameter, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "SET_VALUE failed with %s [%s]: %s, %s, %s",
                hhe.name,
                reduce_args(args=hhe.args),
                channel_address,
                parameter,
                value,
            )
            return False
        return True

    async def set_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> bool:
        """Set single value on paramset VALUES."""
        if paramset_key == HmParamsetKey.VALUES:
            return await self._set_value(
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                rx_mode=rx_mode,
            )
        return await self.put_paramset(
            address=channel_address,
            paramset_key=paramset_key,
            value={parameter: value},
            rx_mode=rx_mode,
        )

    async def get_paramset(self, address: str, paramset_key: str) -> Any:
        """
        Return a paramset from CCU.

        Address is usually the channel_address,
        but for bidcos devices there is a master paramset at the device.
        """
        try:
            _LOGGER.debug(
                "GET_PARAMSET: address %s, paramset_key %s",
                address,
                paramset_key,
            )
            return await self._proxy_read.getParamset(address, paramset_key)
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "GET_PARAMSET failed with %s [%s]: %s, %s",
                hhe.name,
                reduce_args(args=hhe.args),
                address,
                paramset_key,
            )
            raise

    async def put_paramset(
        self,
        address: str,
        paramset_key: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> bool:
        """
        Set paramsets manually.

        Address is usually the channel_address,
        but for bidcos devices there is a master paramset at the device.
        """
        try:
            _LOGGER.debug("PUT_PARAMSET: %s, %s, %s", address, paramset_key, value)
            if rx_mode:
                await self._proxy.putParamset(address, paramset_key, value, rx_mode)
            else:
                await self._proxy.putParamset(address, paramset_key, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "PUT_PARAMSET failed: %s [%s] %s, %s, %s",
                hhe.name,
                reduce_args(args=hhe.args),
                address,
                paramset_key,
                value,
            )
            return False
        return True

    async def fetch_paramset_description(
        self, channel_address: str, paramset_key: str, save_to_file: bool = True
    ) -> None:
        """Fetch a specific paramset and add it to the known ones."""
        _LOGGER.debug("FETCH_PARAMSET_DESCRIPTION: %s for %s", paramset_key, channel_address)

        try:
            parameter_data = await self._get_paramset_description(
                address=channel_address, paramset_key=paramset_key
            )
            self.central.paramset_descriptions.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=parameter_data,
            )
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "FETCH_PARAMSET_DESCRIPTION failed: "
                "%s [%s] Unable to get paramset %s for channel_address %s",
                hhe.name,
                reduce_args(args=hhe.args),
                paramset_key,
                channel_address,
            )
        if save_to_file:
            await self.central.paramset_descriptions.save()

    async def fetch_paramset_descriptions(self, device_description: dict[str, Any]) -> None:
        """Fetch paramsets for provided device description."""
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self.central.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=paramset_key,
                    paramset_description=paramset_description,
                )

    async def get_paramset_descriptions(
        self, device_description: dict[str, Any], only_relevant: bool = True
    ) -> dict[str, dict[str, Any]]:
        """Get paramsets for provided device description."""
        if not device_description:
            return {}
        paramsets: dict[str, dict[str, Any]] = {}
        address = device_description[HmDescription.ADDRESS]
        paramsets[address] = {}
        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS for %s", address)
        for paramset_key in device_description.get(HmDescription.PARAMSETS, []):
            if (channel_no := get_channel_no(address)) is None:
                # No paramsets at root device
                continue

            device_type = (
                device_description[HmDescription.TYPE]
                if channel_no is None
                else device_description[HmDescription.PARENT_TYPE]
            )
            if (
                only_relevant
                and channel_no
                and not self.central.parameter_visibility.is_relevant_paramset(
                    device_type=device_type,
                    channel_no=channel_no,
                    paramset_key=paramset_key,
                )
            ):
                continue
            try:
                paramsets[address][paramset_key] = await self._get_paramset_description(
                    address=address, paramset_key=paramset_key
                )
            except BaseHomematicException as hhe:
                _LOGGER.warning(
                    "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                    hhe.name,
                    reduce_args(args=hhe.args),
                    paramset_key,
                    address,
                )
        return paramsets

    async def _get_paramset_description(self, address: str, paramset_key: str) -> Any:
        """Get paramset description from CCU."""
        return await self._proxy_read.getParamsetDescription(address, paramset_key)

    async def get_all_paramset_descriptions(
        self, device_descriptions: list[dict[str, Any]]
    ) -> dict[str, dict[str, Any]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[str, Any]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(
                await self.get_paramset_descriptions(
                    device_description=device_description, only_relevant=False
                )
            )
        return all_paramsets

    async def update_device_firmware(self, device_address: str) -> bool:
        """Update the firmware of a homematic device."""
        if device := self.central.get_device(address=device_address):
            _LOGGER.info(
                "UPDATE_DEVICE_FIRMWARE: Trying firmware update for %s",
                device_address,
            )
            try:
                update_result = (
                    await self._proxy.installFirmware(device_address)
                    if device.product_group in (HmProductGroup.HMIPW, HmProductGroup.HMIP)
                    else await self._proxy.updateFirmware(device_address)
                )
                result = (
                    bool(update_result)
                    if isinstance(update_result, bool)
                    else bool(update_result[0])
                )
                _LOGGER.info(
                    "UPDATE_DEVICE_FIRMWARE: Executed firmware update for %s with result '%s'",
                    device_address,
                    "success" if result else "failed",
                )
                return result
            except BaseHomematicException as bex:
                _LOGGER.warning(
                    "UPDATE_DEVICE_FIRMWARE failed: %s [%s]",
                    bex.name,
                    reduce_args(args=bex.args),
                )
        return False

    async def update_paramset_descriptions(self, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        if not self.central.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: "
                "Interface missing in central_unit cache. "
                "Not updating paramsets for %s",
                device_address,
            )
            return
        if not self.central.device_descriptions.get_device(
            interface_id=self.interface_id, device_address=device_address
        ):
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: "
                "Channel missing in central_unit.cache. "
                "Not updating paramsets for %s",
                device_address,
            )
            return
        await self.fetch_paramset_descriptions(
            self.central.device_descriptions.get_device(
                interface_id=self.interface_id, device_address=device_address
            ),
        )
        await self.central.paramset_descriptions.save()


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return HmBackend.CCU

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return True

    @measure_execution_time
    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPS and store in data.NAMES."""
        if json_result := await self._json_rpc_client.get_device_details():
            for device in json_result:
                self.central.device_details.add_name(
                    address=device[ATTR_ADDRESS], name=device[ATTR_NAME]
                )
                self.central.device_details.add_device_channel_id(
                    address=device[ATTR_ADDRESS], channel_id=device[ATTR_ID]
                )
                for channel in device.get(ATTR_CHANNELS, []):
                    self.central.device_details.add_name(
                        address=channel[ATTR_ADDRESS], name=channel[ATTR_NAME]
                    )
                    self.central.device_details.add_device_channel_id(
                        address=channel[ATTR_ADDRESS], channel_id=channel[ATTR_ID]
                    )
                self.central.device_details.add_interface(
                    device[ATTR_ADDRESS], device[ATTR_INTERFACE]
                )
        else:
            _LOGGER.debug("FETCH_DEVICE_DETAILS: Unable to fetch device details via JSON-RPC")

    @measure_execution_time
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""
        if device_data := await self._json_rpc_client.get_all_device_data():
            _LOGGER.debug("FETCH_ALL_DEVICE_DATA: Fetched all device data")
            self.central.device_data.add_device_data(device_data=device_data)
        else:
            _LOGGER.debug(
                "FETCH_ALL_DEVICE_DATA: Unable to get all device data via JSON-RPC RegaScript"
            )

    async def check_connection_availability(self) -> bool:
        """Check if _proxy is still initialized."""
        try:
            await self._proxy.ping(self.interface_id)
            self.last_updated = datetime.now()
            self.central.increase_ping_count(interface_id=self.interface_id)
            return True
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                hhe.name,
                reduce_args(args=hhe.args),
            )
        self.last_updated = INIT_DATETIME
        return False

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU."""
        return await self._json_rpc_client.execute_program(pid=pid)

    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        return await self._json_rpc_client.set_system_variable(name=name, value=value)

    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        return await self._json_rpc_client.delete_system_variable(name=name)

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        return await self._json_rpc_client.get_system_variable(name=name)

    async def get_all_system_variables(self, include_internal: bool) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        return await self._json_rpc_client.get_all_system_variables(
            include_internal=include_internal
        )

    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get all programs, if available."""
        return await self._json_rpc_client.get_all_programs(include_internal=include_internal)

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from CCU."""
        rooms: dict[str, set[str]] = {}
        channel_ids_room = await self._json_rpc_client.get_all_channel_ids_room()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if names := channel_ids_room.get(channel_id):
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from CCU."""
        functions: dict[str, set[str]] = {}
        channel_ids_function = await self._json_rpc_client.get_all_channel_ids_function()
        for address, channel_id in self.central.device_details.device_channel_ids.items():
            if sections := channel_ids_function.get(channel_id):
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(
            available_interfaces=await self._json_rpc_client.get_available_interfaces(),
            auth_enabled=await self._json_rpc_client.get_auth_enabled(),
            https_redirect_enabled=await self._json_rpc_client.get_https_redirect_enabled(),
            serial=await self._json_rpc_client.get_serial(),
        )


class ClientHomegear(Client):
    """Client implementation for Homegear backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        if self._config.version:
            return (
                HmBackend.PYDEVCCU
                if HmBackend.PYDEVCCU.lower() in self._config.version
                else HmBackend.HOMEGEAR
            )
        return HmBackend.CCU

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return False

    @measure_execution_time
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""
        return

    @measure_execution_time
    async def fetch_device_details(self) -> None:
        """Get all names from metadata (Homegear)."""
        _LOGGER.debug("FETCH_DEVICE_DETAILS: Fetching names via Metadata")
        for address in self.central.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            try:
                self.central.device_details.add_name(
                    address,
                    await self._proxy_read.getMetadata(address, HmDescription.NAME),
                )
            except BaseHomematicException as hhe:
                _LOGGER.warning(
                    "%s [%s] Failed to fetch name for device %s",
                    hhe.name,
                    reduce_args(args=hhe.args),
                    address,
                )

    async def check_connection_availability(self) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.last_updated = datetime.now()
            if self.supports_ping_pong:
                self.central.increase_ping_count(interface_id=self.interface_id)
            return True
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                hhe.name,
                reduce_args(args=hhe.args),
            )
        self.last_updated = INIT_DATETIME
        return False

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on Homegear."""
        return True

    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        try:
            await self._proxy.setSystemVariable(name, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "SET_SYSTEM_VARIABLE failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
            return False
        return True

    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        try:
            await self._proxy.deleteSystemVariable(name)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "DELETE_SYSTEM_VARIABLE failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
            return False
        return True

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        try:
            return await self._proxy.getSystemVariable(name)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "GET_SYSTEM_VARIABLE failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )

    async def get_all_system_variables(self, include_internal: bool) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        variables: list[SystemVariableData] = []
        try:
            if hg_variables := await self._proxy.getAllSystemVariables():
                for name, value in hg_variables.items():
                    variables.append(SystemVariableData(name=name, value=value))
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "GET_ALL_SYSTEM_VARIABLES failed: %s [%s]", hhe.name, reduce_args(args=hhe.args)
            )
        return variables

    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get all programs, if available."""
        return []

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from Homegear."""
        return {}

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from Homegear."""
        return {}

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(available_interfaces=[IF_BIDCOS_RF_NAME], serial=HOMEGEAR_SERIAL)


class _ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        interface_config: InterfaceConfig,
        local_ip: str,
    ) -> None:
        self.central: Final = central
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self._callback_host: Final[str] = (
            central.config.callback_host if central.config.callback_host else local_ip
        )
        self._callback_port: Final[int] = (
            central.config.callback_port if central.config.callback_port else central.local_port
        )
        self.has_credentials: Final[bool] = (
            central.config.username is not None and central.config.password is not None
        )
        self.init_url: Final[str] = f"http://{self._callback_host}:{self._callback_port}"
        self.xml_rpc_uri: Final = build_xml_rpc_uri(
            host=central.config.host,
            port=interface_config.port,
            path=interface_config.remote_path,
            tls=central.config.tls,
        )

    async def get_client(self) -> Client:
        """Identify the used client."""
        client: Client | None = None
        check_proxy = self._get_simple_xml_rpc_proxy()
        try:
            if methods := await check_proxy.system.listMethods():
                # BidCos-Wired does not support getVersion()
                self.version = (
                    cast(str, await check_proxy.getVersion()) if "getVersion" in methods else "0"
                )

            if client := (
                ClientHomegear(client_config=self)
                if "Homegear" in self.version or "pydevccu" in self.version
                else ClientCCU(client_config=self)
            ):
                await client.init_client()
                if await client.check_connection_availability():
                    return client
            raise NoConnection(f"No connection to {self.interface_id}")
        except (AuthFailure, NoConnection):
            raise
        except Exception as exc:
            raise NoConnection(f"Unable to connect {reduce_args(args=exc.args)}.") from exc

    def get_xml_rpc_proxy(self, auth_enabled: bool | None = None) -> XmlRpcProxy:
        """Return a XmlRPC proxy for backend communication."""
        central_config = self.central.config
        xml_rpc_headers = (
            build_headers(
                username=central_config.username,
                password=central_config.password,
            )
            if auth_enabled
            else []
        )
        return XmlRpcProxy(
            max_workers=1,
            interface_id=self.interface_id,
            connection_state=central_config.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=central_config.tls,
            verify_tls=central_config.verify_tls,
        )

    def _get_simple_xml_rpc_proxy(self) -> XmlRpcProxy:
        """Return a XmlRPC proxy for backend communication."""
        central_config = self.central.config
        xml_rpc_headers = build_headers(
            username=central_config.username,
            password=central_config.password,
        )
        return XmlRpcProxy(
            max_workers=0,
            interface_id=self.interface_id,
            connection_state=central_config.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=central_config.tls,
            verify_tls=central_config.verify_tls,
        )


class InterfaceConfig:
    """interface config for a Client."""

    def __init__(
        self,
        central_name: str,
        interface: HmInterface,
        port: int,
        remote_path: str | None = None,
    ) -> None:
        """Init the interface config."""
        self.interface: Final[HmInterface] = interface
        self.interface_id: Final[str] = f"{central_name}-{self.interface}"
        self.port: Final = port
        self.remote_path: Final = remote_path
        self.validate()

    def validate(self) -> None:
        """Validate the client_config."""
        if self.interface not in IF_NAMES:
            _LOGGER.warning(
                "VALIDATE interface config failed: "
                "Interface names must be within [%s] for production use",
                ", ".join(IF_NAMES),
            )


async def create_client(
    central: hmcu.CentralUnit,
    interface_config: InterfaceConfig,
    local_ip: str,
) -> Client:
    """Return a new client for with a given interface_config."""
    return await _ClientConfig(
        central=central, interface_config=interface_config, local_ip=local_ip
    ).get_client()


def get_client(interface_id: str) -> Client | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.has_client(interface_id=interface_id):
            return central.get_client(interface_id=interface_id)
    return None
