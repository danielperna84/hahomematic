"""The client-object and its methods."""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic import config
import hahomematic.central_unit as hm_central
from hahomematic.config import CHECK_INTERVAL
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CHANNELS,
    ATTR_HM_ADDRESS,
    ATTR_HM_NAME,
    ATTR_HM_PARAMSETS,
    ATTR_HM_PARENT_TYPE,
    ATTR_HM_TYPE,
    ATTR_ID,
    ATTR_INTERFACE,
    ATTR_NAME,
    ATTR_SUBTYPE,
    BACKEND_CCU,
    BACKEND_HOMEGEAR,
    BACKEND_PYDEVCCU,
    HM_VIRTUAL_REMOTE_TYPES,
    IF_BIDCOS_RF_NAME,
    IF_NAMES,
    INIT_DATETIME,
    PARAMSET_KEY_MASTER,
    PARAMSET_KEY_VALUES,
    PROXY_DE_INIT_FAILED,
    PROXY_DE_INIT_SKIPPED,
    PROXY_DE_INIT_SUCCESS,
    PROXY_INIT_FAILED,
    PROXY_INIT_SUCCESS,
    HmCallSource,
    HmForcedDeviceAvailability,
    HmInterfaceEventType,
)
from hahomematic.device import HmDevice
from hahomematic.exceptions import (
    AuthFailure,
    BaseHomematicException,
    HaHomematicException,
    NoConnection,
)
from hahomematic.helpers import (
    ProgramData,
    SystemVariableData,
    build_headers,
    build_xml_rpc_uri,
    get_channel_no,
)
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.xml_rpc_proxy import XmlRpcProxy

_LOGGER = logging.getLogger(__name__)


class Client(ABC):
    """
    Client object that initializes the XML-RPC proxy
    and provides access to other data via XML-RPC
    or JSON-RPC.
    """

    def __init__(self, client_config: _ClientConfig):
        """
        Initialize the Client.
        """
        self.config: Final[_ClientConfig] = client_config
        self.central: Final[hm_central.CentralUnit] = client_config.central
        # This is the actual interface_id used for init
        self.interface_id: Final[str] = client_config.interface_id
        # for all device related interaction
        self._proxy: Final[XmlRpcProxy] = client_config.xml_rpc_proxy
        self._proxy_read: Final[XmlRpcProxy] = client_config.xml_rpc_proxy_read
        self._json_rpc_client: Final[
            JsonRpcAioHttpClient
        ] = self.central.json_rpc_client

        self._is_callback_alive: bool = True
        self._available: bool = True
        self.last_updated: datetime = INIT_DATETIME
        self._connection_error_count: int = 0

    @property
    def available(self) -> bool:
        """Return the availability of the client."""
        return self._available

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return ""

    async def proxy_init(self) -> int:
        """
        To receive events the proxy has to tell the CCU / Homegear
        where to send the events. For that we call the init-method.
        """
        try:
            _LOGGER.debug(
                "proxy_init: init('%s', '%s')", self.config.init_url, self.interface_id
            )
            await self._proxy.init(self.config.init_url, self.interface_id)
            self._mark_all_devices_forced_availability(
                forced_availability=HmForcedDeviceAvailability.NOT_SET
            )
            _LOGGER.debug("proxy_init: Proxy for %s initialized", self.interface_id)
        except BaseHomematicException as hhe:
            _LOGGER.error(
                "proxy_init failed: %s [%s] Unable to initialize proxy for %s",
                hhe.name,
                hhe.args,
                self.interface_id,
            )
            self.last_updated = INIT_DATETIME
            return PROXY_INIT_FAILED
        self.last_updated = datetime.now()
        return PROXY_INIT_SUCCESS

    async def proxy_de_init(self) -> int:
        """
        De-init to stop CCU from sending events for this remote.
        """
        if self.last_updated == INIT_DATETIME:
            _LOGGER.debug(
                "proxy_de_init: Skipping de-init for %s (not initialized)",
                self.interface_id,
            )
            return PROXY_DE_INIT_SKIPPED
        try:
            _LOGGER.debug("proxy_de_init: init('%s')", self.config.init_url)
            await self._proxy.init(self.config.init_url)
        except BaseHomematicException as hhe:
            _LOGGER.error(
                "proxy_de_init failed: %s [%s] Unable to de-initialize proxy for %s",
                hhe.name,
                hhe.args,
                self.interface_id,
            )
            return PROXY_DE_INIT_FAILED

        self.last_updated = INIT_DATETIME
        return PROXY_DE_INIT_SUCCESS

    async def proxy_re_init(self) -> int:
        """Reinit Proxy"""
        if PROXY_DE_INIT_FAILED != await self.proxy_de_init():
            return await self.proxy_init()
        return PROXY_DE_INIT_FAILED

    def _mark_all_devices_forced_availability(
        self, forced_availability: HmForcedDeviceAvailability
    ) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != HmForcedDeviceAvailability.FORCE_FALSE
        if self._available != available:
            for hm_device in self.central.hm_devices.values():
                if hm_device.interface_id == self.interface_id:
                    hm_device.set_forced_availability(
                        forced_availability=forced_availability
                    )
            self._available = available
            _LOGGER.warning(
                "mark_all_devices_availability: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )
        self.central.fire_interface_event(
            interface_id=self.interface_id,
            interface_event_type=HmInterfaceEventType.PROXY,
            available=available,
        )

    async def reconnect(self) -> bool:
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.warning(
                "reconnect: waiting to re-connect client %s for %is",
                self.interface_id,
                int(config.RECONNECT_WAIT),
            )
            await asyncio.sleep(config.RECONNECT_WAIT)

            await self.proxy_re_init()
            _LOGGER.warning(
                "reconnect: re-connected client %s",
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
        """fetch all device data from CCU."""

    @abstractmethod
    async def fetch_device_details(self) -> None:
        """Fetch names from backend."""

    async def is_connected(self) -> bool:
        """
        Perform actions required for connectivity check.
        Connection is not connected, if three consecutive checks fail.
        Return connectivity state.
        """
        if await self._check_connection_availability() is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        if self._connection_error_count > 3:
            self._mark_all_devices_forced_availability(
                forced_availability=HmForcedDeviceAvailability.FORCE_FALSE
            )
            return False

        if (datetime.now() - self.last_updated).total_seconds() < CHECK_INTERVAL:
            return True
        return False

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if last_events_time := self.central.last_events.get(self.interface_id):
            seconds_since_last_event = (
                datetime.now() - last_events_time
            ).total_seconds()
            if seconds_since_last_event > CHECK_INTERVAL:
                if self._is_callback_alive:
                    self.central.fire_interface_event(
                        interface_id=self.interface_id,
                        interface_event_type=HmInterfaceEventType.CALLBACK,
                        available=False,
                    )
                    self._is_callback_alive = False
                _LOGGER.warning(
                    "is_callback_alive: Callback for %s has not received events for %i seconds')",
                    self.interface_id,
                    seconds_since_last_event,
                )
                return False

            if not self._is_callback_alive:
                self.central.fire_interface_event(
                    interface_id=self.interface_id,
                    interface_event_type=HmInterfaceEventType.CALLBACK,
                    available=True,
                )
                self._is_callback_alive = True
        return True

    @abstractmethod
    async def _check_connection_availability(self) -> bool:
        """Send ping to CCU to generate PONG event."""

    @abstractmethod
    async def execute_program(self, pid: str) -> None:
        """Execute a program on CCU / Homegear."""

    @abstractmethod
    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""

    @abstractmethod
    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""

    @abstractmethod
    async def get_system_variable(self, name: str) -> str:
        """Get single system variable from CCU / Homegear."""

    @abstractmethod
    async def get_all_system_variables(
        self, include_internal: bool
    ) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""

    @abstractmethod
    async def get_available_interfaces(self) -> list[str]:
        """Get all available interfaces from CCU / Homegear."""

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
    async def get_serial(self) -> str:
        """Get the serial of the backend."""

    @abstractmethod
    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""

    async def get_all_device_descriptions(self) -> Any:
        """Get device descriptions from CCU / Homegear."""
        try:
            return await self._proxy.listDevices()
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_all_devices failed: %s [%s]", hhe.name, hhe.args)
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
        except BaseHomematicException as hhe:
            _LOGGER.warning("set_install_mode failed: %s [%s]", hhe.name, hhe.args)

    async def get_install_mode(self) -> Any:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return await self._proxy.getInstallMode()
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_install_mode failed: %s [%s]", hhe.name, hhe.args)
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
                "get_value: channel_address %s, parameter %s, paramset_key, %s, source:%s",
                channel_address,
                parameter,
                paramset_key,
                call_source,
            )
            if paramset_key == PARAMSET_KEY_VALUES:
                return await self._proxy_read.getValue(channel_address, parameter)
            paramset = (
                await self._proxy_read.getParamset(channel_address, PARAMSET_KEY_MASTER)
                or {}
            )
            return paramset.get(parameter)
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "get_value failed with %s [%s]: %s, %s, %s",
                hhe.name,
                hhe.args,
                channel_address,
                parameter,
                paramset_key,
            )
            raise HaHomematicException from hhe

    async def _set_value(
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
            _LOGGER.debug("_set_value: %s, %s, %s", channel_address, parameter, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "_set_value failed with %s [%s]: %s, %s, %s",
                hhe.name,
                hhe.args,
                channel_address,
                parameter,
                value,
            )

    async def set_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set single value on paramset VALUES."""
        if paramset_key == PARAMSET_KEY_VALUES:
            await self._set_value(
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                rx_mode=rx_mode,
            )
            return
        await self.put_paramset(
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
                "get_paramset: address %s, paramset_key %s",
                address,
                paramset_key,
            )
            return await self._proxy_read.getParamset(address, paramset_key)
        except BaseHomematicException as hhe:
            _LOGGER.debug(
                "get_paramset failed with %s [%s]: %s, %s",
                hhe.name,
                hhe.args,
                address,
                paramset_key,
            )
            raise HaHomematicException from hhe

    async def put_paramset(
        self,
        address: str,
        paramset_key: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """
        Set paramsets manually.
        Address is usually the channel_address,
        but for bidcos devices there is a master paramset at the device.
        """
        try:
            if rx_mode:
                await self._proxy.putParamset(address, paramset_key, value, rx_mode)
            else:
                await self._proxy.putParamset(address, paramset_key, value)
            _LOGGER.debug("put_paramset: %s, %s, %s", address, paramset_key, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "put_paramset failed: %s [%s] %s, %s, %s",
                hhe.name,
                hhe.args,
                address,
                paramset_key,
                value,
            )

    async def fetch_paramset_description(
        self, channel_address: str, paramset_key: str, save_to_file: bool = True
    ) -> None:
        """
        Fetch a specific paramset and add it to the known ones.
        """
        _LOGGER.debug(
            "fetch_paramset_description: %s for %s", paramset_key, channel_address
        )

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
                "fetch_paramset_description failed: %s [%s] Unable to get paramset %s for channel_address %s",
                hhe.name,
                hhe.args,
                paramset_key,
                channel_address,
            )
        if save_to_file:
            await self.central.paramset_descriptions.save()

    async def fetch_paramset_descriptions(
        self, device_description: dict[str, Any]
    ) -> None:
        """
        Fetch paramsets for provided device description.
        """
        data = await self.get_paramset_descriptions(
            device_description=device_description
        )
        for address, paramsets in data.items():
            _LOGGER.debug("fetch_paramset_descriptions for %s", address)
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
        address = device_description[ATTR_HM_ADDRESS]
        sub_type = device_description.get(ATTR_SUBTYPE)
        paramsets[address] = {}
        _LOGGER.debug("get_paramset_descriptions for %s", address)
        for paramset_key in device_description.get(ATTR_HM_PARAMSETS, []):
            if (device_channel := get_channel_no(address)) is None:
                # No paramsets at root device
                continue

            device_type = (
                device_description[ATTR_HM_TYPE]
                if device_channel is None
                else device_description[ATTR_HM_PARENT_TYPE]
            )
            if (
                only_relevant
                and device_channel
                and not self.central.parameter_visibility.is_relevant_paramset(
                    device_type=device_type,
                    sub_type=sub_type,
                    device_channel=device_channel,
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
                    "get_paramsets failed with %s [%s] for %s address %s.",
                    hhe.name,
                    hhe.args,
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

    async def update_paramset_descriptions(self, device_address: str) -> None:
        """
        Update paramsets descriptions for provided device_address.
        """
        if not self.central.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            _LOGGER.warning(
                "update_paramset_descriptions failed: Interface missing in central_unit cache. Not updating paramsets for %s.",
                device_address,
            )
            return
        if not self.central.device_descriptions.get_device(
            interface_id=self.interface_id, device_address=device_address
        ):
            _LOGGER.warning(
                "update_paramset_descriptions failed: Channel missing in central_unit.cache. Not updating paramsets for %s.",
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
        return BACKEND_CCU

    async def fetch_device_details(self) -> None:
        """
        Get all names via JSON-RPS and store in data.NAMES.
        """
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
            _LOGGER.debug(
                "fetch_names_json: Unable to fetch device details via JSON-RPC."
            )

    async def fetch_all_device_data(self) -> None:
        """fetch all device data from CCU."""
        if device_data := await self._json_rpc_client.get_all_device_data():
            _LOGGER.debug("fetch_all_device_data: Fetched all device data.")
            self.central.device_data.add_device_data(device_data=device_data)
        else:
            _LOGGER.debug(
                "fetch_all_device_data: Unable to get all device data via JSON-RPC RegaScript."
            )

    async def _check_connection_availability(self) -> bool:
        """Check if _proxy is still initialized."""
        try:
            await self._proxy.ping(self.interface_id)
            self.last_updated = datetime.now()
            return True
        except BaseHomematicException as hhe:
            _LOGGER.error("ping failed: %s [%s]", hhe.name, hhe.args)
        self.last_updated = INIT_DATETIME
        return False

    async def execute_program(self, pid: str) -> None:
        """Execute a program on CCU."""
        await self._json_rpc_client.execute_program(pid=pid)

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        await self._json_rpc_client.set_system_variable(name=name, value=value)

    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        await self._json_rpc_client.delete_system_variable(name=name)

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        return await self._json_rpc_client.get_system_variable(name=name)

    async def get_all_system_variables(
        self, include_internal: bool
    ) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        return await self._json_rpc_client.get_all_system_variables(
            include_internal=include_internal
        )

    async def get_available_interfaces(self) -> list[str]:
        """Get all available interfaces from CCU / Homegear."""
        return await self._json_rpc_client.get_available_interfaces()

    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get all programs, if available."""
        return await self._json_rpc_client.get_all_programs(
            include_internal=include_internal
        )

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from CCU."""
        rooms: dict[str, set[str]] = {}
        device_channel_ids = self.central.device_details.device_channel_ids
        channel_ids_room = await self._json_rpc_client.get_all_channel_ids_room()
        for address, channel_id in device_channel_ids.items():
            if names := channel_ids_room.get(channel_id):
                if address not in rooms:
                    rooms[address] = set()
                rooms[address].update(names)
        return rooms

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from CCU."""
        functions: dict[str, set[str]] = {}
        device_channel_ids = self.central.device_details.device_channel_ids
        channel_ids_function = (
            await self._json_rpc_client.get_all_channel_ids_function()
        )
        for address, channel_id in device_channel_ids.items():
            if sections := channel_ids_function.get(channel_id):
                if address not in functions:
                    functions[address] = set()
                functions[address].update(sections)
        return functions

    async def get_serial(self) -> str:
        """Get the serial of the backend."""
        return await self._json_rpc_client.get_serial()

    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for device_type in HM_VIRTUAL_REMOTE_TYPES:
            for hm_device in self.central.hm_devices.values():
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
        if self.config.version:
            return (
                BACKEND_PYDEVCCU
                if BACKEND_PYDEVCCU.lower() in self.config.version
                else BACKEND_HOMEGEAR
            )
        return BACKEND_CCU

    async def fetch_all_device_data(self) -> None:
        """fetch all device data from CCU."""
        return

    async def fetch_device_details(self) -> None:
        """
        Get all names from metadata (Homegear).
        """
        _LOGGER.debug("fetch_names_metadata: Fetching names via Metadata.")
        for address in self.central.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            try:
                self.central.device_details.add_name(
                    address,
                    await self._proxy_read.getMetadata(address, ATTR_HM_NAME),
                )
            except BaseHomematicException as hhe:
                _LOGGER.warning(
                    "%s [%s] Failed to fetch name for device %s",
                    hhe.name,
                    hhe.args,
                    address,
                )

    async def _check_connection_availability(self) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.last_updated = datetime.now()
            return True
        except BaseHomematicException as hhe:
            _LOGGER.error("ping failed: %s [%s]", hhe.name, hhe.args)
        self.last_updated = INIT_DATETIME
        return False

    async def execute_program(self, pid: str) -> None:
        """Execute a program on Homegear."""
        return None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        try:
            await self._proxy.setSystemVariable(name, value)
        except BaseHomematicException as hhe:
            _LOGGER.warning("set_system_variable failed: %s [%s]", hhe.name, hhe.args)

    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        try:
            await self._proxy.deleteSystemVariable(name)
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "delete_system_variable failed: %s [%s]", hhe.name, hhe.args
            )

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        try:
            return await self._proxy.getSystemVariable(name)
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_system_variable failed: %s [%s]", hhe.name, hhe.args)

    async def get_all_system_variables(
        self, include_internal: bool
    ) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        variables: list[SystemVariableData] = []
        try:
            if hg_variables := await self._proxy.getAllSystemVariables():
                for name, value in hg_variables.items():
                    variables.append(SystemVariableData(name=name, value=value))
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "get_all_system_variables failed: %s [%s]", hhe.name, hhe.args
            )
        return variables

    async def get_available_interfaces(self) -> list[str]:
        """Get all available interfaces from CCU / Homegear."""
        return [IF_BIDCOS_RF_NAME]

    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get all programs, if available."""
        return []

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from Homegear."""
        return {}

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from Homegear."""
        return {}

    async def get_serial(self) -> str:
        """Get the serial of the backend."""
        return "Homegear_SN0815"

    def get_virtual_remote(self) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        return None


class _ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        central: hm_central.CentralUnit,
        interface_config: InterfaceConfig,
        local_ip: str,
    ):
        self.central: Final[hm_central.CentralUnit] = central
        self.interface_config: Final[InterfaceConfig] = interface_config
        self.interface: Final[str] = interface_config.interface
        self.interface_id: Final[str] = interface_config.interface_id
        self._callback_host: Final[str] = (
            central.config.callback_host if central.config.callback_host else local_ip
        )
        self._callback_port: Final[int] = (
            central.config.callback_port
            if central.config.callback_port
            else central.local_port
        )
        self.has_credentials: Final[bool] = (
            central.config.username is not None and central.config.password is not None
        )
        self.init_url: Final[
            str
        ] = f"http://{self._callback_host}:{self._callback_port}"
        self.xml_rpc_uri: Final[str] = build_xml_rpc_uri(
            host=central.config.host,
            port=interface_config.port,
            path=interface_config.path,
            tls=central.config.tls,
        )
        self.xml_rpc_headers: Final[list[tuple[str, str]]] = build_headers(
            username=central.config.username,
            password=central.config.password,
        )
        self.xml_rpc_proxy: Final[XmlRpcProxy] = XmlRpcProxy(
            central.loop,
            max_workers=1,
            thread_name_prefix=f"XmlRpcProxy for {self.interface_id}",
            uri=self.xml_rpc_uri,
            headers=self.xml_rpc_headers,
            tls=central.config.tls,
            verify_tls=central.config.verify_tls,
        )
        self.xml_rpc_proxy_read: Final[XmlRpcProxy] = XmlRpcProxy(
            central.loop,
            max_workers=1,
            thread_name_prefix=f"XmlRpcProxyRead for {self.interface_id}",
            uri=self.xml_rpc_uri,
            headers=self.xml_rpc_headers,
            tls=central.config.tls,
            verify_tls=central.config.verify_tls,
        )
        self.version: str = "0"
        self.serial: str = "0"

    async def get_client(self) -> Client:
        """Identify the used client."""

        try:
            client: Client | None = None
            methods = await self.xml_rpc_proxy.system.listMethods()
            if "getVersion" not in methods:
                # BidCos-Wired does not support getVersion()
                client = ClientCCU(self)
            elif version := await self.xml_rpc_proxy.getVersion():
                self.version = cast(str, version)
                if "Homegear" in version or "pydevccu" in version:
                    client = ClientHomegear(self)
            if not client:
                client = ClientCCU(self)
            self.serial = await client.get_serial()
            return client
        except AuthFailure as auf:
            raise AuthFailure(f"Unable to authenticate {auf.args}.") from auf
        except Exception as noc:
            raise NoConnection(f"Unable to connect {noc.args}.") from noc


class InterfaceConfig:
    """interface config for a Client."""

    def __init__(
        self,
        central_name: str,
        interface: str,
        port: int,
        path: str | None = None,
    ):
        self.interface: Final[str] = interface
        self.interface_id = f"{central_name}-{interface}"
        self.port: Final[int] = port
        self.path: Final[str | None] = path
        self.validate()

    def validate(self) -> None:
        """Validate the client_config."""
        if self.interface not in IF_NAMES:
            _LOGGER.warning(
                "InterfaceConfig: Interface names must be within [%s] ",
                ", ".join(IF_NAMES),
            )


async def create_client(
    central: hm_central.CentralUnit,
    interface_config: InterfaceConfig,
    local_ip: str,
) -> Client:
    """Return a new client for with a given interface_config."""
    return await _ClientConfig(
        central=central, interface_config=interface_config, local_ip=local_ip
    ).get_client()


def get_client_by_interface_id(interface_id: str) -> Client | None:
    """Return client by interface_id"""
    for central in hm_central.CENTRAL_INSTANCES.values():
        if client := central.get_client_by_interface_id(interface_id=interface_id):
            return client
    return None
