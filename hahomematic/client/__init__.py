"""The client-object and its methods."""

from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic import central as hmcu
from hahomematic.caches.dynamic import CommandCache, PingPongCache
from hahomematic.client.xml_rpc import XmlRpcProxy
from hahomematic.config import CALLBACK_WARN_INTERVAL, RECONNECT_WAIT, WAIT_FOR_CALLBACK
from hahomematic.const import (
    DATETIME_FORMAT_MILLIS,
    DEFAULT_CUSTOM_ID,
    DEFAULT_MAX_WORKERS,
    ENTITY_KEY,
    EVENT_AVAILABLE,
    EVENT_SECONDS_SINCE_LAST_EVENT,
    HOMEGEAR_SERIAL,
    INIT_DATETIME,
    INTERFACES_SUPPORTING_FIRMWARE_UPDATES,
    VIRTUAL_REMOTE_MODELS,
    Backend,
    CallSource,
    CommandRxMode,
    DeviceDescription,
    ForcedDeviceAvailability,
    InterfaceEventType,
    InterfaceName,
    Operations,
    ParameterData,
    ParamsetKey,
    ProductGroup,
    ProgramData,
    ProxyInitState,
    SystemInformation,
    SystemVariableData,
)
from hahomematic.exceptions import BaseHomematicException, ClientException, NoConnection
from hahomematic.performance import measure_execution_time
from hahomematic.platforms.decorators import service
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.support import convert_value
from hahomematic.support import (
    build_headers,
    build_xml_rpc_uri,
    get_device_address,
    is_channel_address,
    is_paramset_key,
    reduce_args,
    supports_rx_mode,
)

__all__ = ["Client", "InterfaceConfig", "create_client", "get_client"]

_LOGGER: Final = logging.getLogger(__name__)

_JSON_ADDRESS: Final = "address"
_JSON_CHANNELS: Final = "channels"
_JSON_ID: Final = "id"
_JSON_INTERFACE: Final = "interface"
_JSON_NAME: Final = "name"
_NAME: Final = "NAME"


class Client(ABC):
    """Client object to access the backends via XML-RPC or JSON-RPC."""

    def __init__(self, client_config: _ClientConfig) -> None:
        """Initialize the Client."""
        self._config: Final = client_config
        self._last_value_send_cache = CommandCache(interface_id=client_config.interface_id)
        self._json_rpc_client: Final = client_config.central.config.json_rpc_client
        self._available: bool = True
        self._connection_error_count: int = 0
        self._is_callback_alive: bool = True
        self._ping_pong_cache: Final = PingPongCache(
            central=client_config.central, interface_id=client_config.interface_id
        )
        self._proxy: XmlRpcProxy
        self._proxy_read: XmlRpcProxy
        self._system_information: SystemInformation
        self.modified_at: datetime = INIT_DATETIME

    async def init_client(self) -> None:
        """Init the client."""
        self._system_information = await self._get_system_information()
        self._proxy = await self._config.get_xml_rpc_proxy(
            auth_enabled=self.system_information.auth_enabled
        )
        self._proxy_read = await self._config.get_xml_rpc_proxy(
            auth_enabled=self.system_information.auth_enabled,
            max_workers=self._config.max_read_workers,
        )

    @property
    def available(self) -> bool:
        """Return the availability of the client."""
        return self._available

    @property
    def central(self) -> hmcu.CentralUnit:
        """Return the central of the client."""
        return self._config.central

    @property
    def interface(self) -> str:
        """Return the interface of the client."""
        return self._config.interface

    @property
    def interface_id(self) -> str:
        """Return the interface id of the client."""
        return self._config.interface_id

    @property
    def last_value_send_cache(self) -> CommandCache:
        """Return the last value send cache."""
        return self._last_value_send_cache

    @property
    @abstractmethod
    def model(self) -> str:
        """Return the model of the backend."""

    @property
    def ping_pong_cache(self) -> PingPongCache:
        """Return the ping pong cache."""
        return self._ping_pong_cache

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the client."""
        return self._system_information

    @property
    def version(self) -> str:
        """Return the version id of the client."""
        return self._config.version

    def get_product_group(self, model: str) -> ProductGroup:
        """Return the product group."""
        if self.interface == InterfaceName.HMIP_RF:
            l_model = model.lower()
            if l_model.startswith("hmipw"):
                return ProductGroup.HMIPW
            if l_model.startswith("hmip"):
                return ProductGroup.HMIP
        if self.interface == InterfaceName.BIDCOS_WIRED:
            return ProductGroup.HMW
        if self.interface == InterfaceName.BIDCOS_RF:
            return ProductGroup.HM
        if self.interface == InterfaceName.VIRTUAL_DEVICES:
            return ProductGroup.VIRTUAL
        return ProductGroup.UNKNOWN

    @property
    @abstractmethod
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""

    @property
    def supports_firmware_updates(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return self.interface in INTERFACES_SUPPORTING_FIRMWARE_UPDATES

    async def proxy_init(self) -> ProxyInitState:
        """Init the proxy has to tell the CCU / Homegear where to send the events."""
        try:
            _LOGGER.debug("PROXY_INIT: init('%s', '%s')", self._config.init_url, self.interface_id)
            self._ping_pong_cache.clear()
            await self._proxy.init(self._config.init_url, self.interface_id)
            self._mark_all_devices_forced_availability(
                forced_availability=ForcedDeviceAvailability.NOT_SET
            )
            _LOGGER.debug("PROXY_INIT: Proxy for %s initialized", self.interface_id)
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "PROXY_INIT failed: %s [%s] Unable to initialize proxy for %s",
                ex.name,
                reduce_args(args=ex.args),
                self.interface_id,
            )
            self.modified_at = INIT_DATETIME
            return ProxyInitState.INIT_FAILED
        self.modified_at = datetime.now()
        return ProxyInitState.INIT_SUCCESS

    async def proxy_de_init(self) -> ProxyInitState:
        """De-init to stop CCU from sending events for this remote."""
        if self.modified_at == INIT_DATETIME:
            _LOGGER.debug(
                "PROXY_DE_INIT: Skipping de-init for %s (not initialized)",
                self.interface_id,
            )
            return ProxyInitState.DE_INIT_SKIPPED
        try:
            _LOGGER.debug("PROXY_DE_INIT: init('%s')", self._config.init_url)
            await self._proxy.init(self._config.init_url)
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "PROXY_DE_INIT failed: %s [%s] Unable to de-initialize proxy for %s",
                ex.name,
                reduce_args(args=ex.args),
                self.interface_id,
            )
            return ProxyInitState.DE_INIT_FAILED

        self.modified_at = INIT_DATETIME
        return ProxyInitState.DE_INIT_SUCCESS

    async def proxy_re_init(self) -> ProxyInitState:
        """Reinit Proxy."""
        if await self.proxy_de_init() != ProxyInitState.DE_INIT_FAILED:
            return await self.proxy_init()
        return ProxyInitState.DE_INIT_FAILED

    def _mark_all_devices_forced_availability(
        self, forced_availability: ForcedDeviceAvailability
    ) -> None:
        """Mark device's availability state for this interface."""
        available = forced_availability != ForcedDeviceAvailability.FORCE_FALSE
        if self._available != available:
            for device in self.central.devices:
                if device.interface_id == self.interface_id:
                    device.set_forced_availability(forced_availability=forced_availability)
            self._available = available
            _LOGGER.debug(
                "MARK_ALL_DEVICES_FORCED_AVAILABILITY: marked all devices %s for %s",
                "available" if available else "unavailable",
                self.interface_id,
            )
        self.central.fire_interface_event(
            interface_id=self.interface_id,
            interface_event_type=InterfaceEventType.PROXY,
            data={EVENT_AVAILABLE: available},
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

    async def stop(self) -> None:
        """Stop depending services."""
        await self._proxy.stop()
        await self._proxy_read.stop()

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
        if await self.check_connection_availability(handle_ping_pong=True) is True:
            self._connection_error_count = 0
        else:
            self._connection_error_count += 1

        if self._connection_error_count > 3:
            self._mark_all_devices_forced_availability(
                forced_availability=ForcedDeviceAvailability.FORCE_FALSE
            )
            return False

        return (datetime.now() - self.modified_at).total_seconds() < CALLBACK_WARN_INTERVAL

    def is_callback_alive(self) -> bool:
        """Return if XmlRPC-Server is alive based on received events for this client."""
        if last_events_time := self.central.last_events.get(self.interface_id):
            seconds_since_last_event = (datetime.now() - last_events_time).total_seconds()
            if seconds_since_last_event > CALLBACK_WARN_INTERVAL:
                if self._is_callback_alive:
                    self.central.fire_interface_event(
                        interface_id=self.interface_id,
                        interface_event_type=InterfaceEventType.CALLBACK,
                        data={
                            EVENT_AVAILABLE: False,
                            EVENT_SECONDS_SINCE_LAST_EVENT: int(seconds_since_last_event),
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
                    interface_event_type=InterfaceEventType.CALLBACK,
                    data={EVENT_AVAILABLE: True},
                )
                self._is_callback_alive = True
        return True

    @abstractmethod
    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Send ping to CCU to generate PONG event."""

    @abstractmethod
    @service()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear.."""

    @abstractmethod
    @service()
    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""

    @abstractmethod
    @service()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""

    @abstractmethod
    @service()
    async def get_system_variable(self, name: str) -> str:
        """Get single system variable from CCU / Homegear."""

    @abstractmethod
    @service()
    async def get_all_system_variables(
        self, include_internal: bool
    ) -> tuple[SystemVariableData, ...]:
        """Get all system variables from CCU / Homegear."""

    @abstractmethod
    async def get_all_programs(self, include_internal: bool) -> tuple[ProgramData, ...]:
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
        for model in VIRTUAL_REMOTE_MODELS:
            for device in self.central.devices:
                if device.interface_id == self.interface_id and device.model == model:
                    return device
        return None

    @measure_execution_time
    async def get_all_device_descriptions(self) -> tuple[DeviceDescription] | None:
        """Get device descriptions from CCU / Homegear."""
        try:
            return tuple(await self._proxy.listDevices())
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "GET_ALL_DEVICE_DESCRIPTIONS failed: %s [%s]", ex.name, reduce_args(args=ex.args)
            )
        return None

    async def get_device_description(self, device_address: str) -> tuple[DeviceDescription] | None:
        """Get device descriptions from CCU / Homegear."""
        try:
            if device_description := await self._proxy_read.getDeviceDescription(device_address):
                return (device_description,)
        except BaseHomematicException as ex:
            _LOGGER.warning(
                "GET_DEVICE_DESCRIPTIONS failed: %s [%s]", ex.name, reduce_args(args=ex.args)
            )
        return None

    @service()
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
        except BaseHomematicException as ex:
            raise ClientException(f"SET_INSTALL_MODE failed: {reduce_args(args=ex.args)}") from ex
        return True

    @service()
    async def get_install_mode(self) -> int:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        try:
            return await self._proxy.getInstallMode()  # type: ignore[no-any-return]
        except BaseHomematicException as ex:
            raise ClientException(f"GET_INSTALL_MODE failed: {reduce_args(args=ex.args)}") from ex

    @service()
    async def add_link(
        self, sender_address: str, receiver_address: str, name: str, description: str
    ) -> None:
        """Return a list of links."""
        try:
            await self._proxy.addLink(sender_address, receiver_address, name, description)
        except BaseHomematicException as ex:
            raise ClientException(
                f"ADD_LINK failed with for: {sender_address}/{receiver_address}/{name}/{description}: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def remove_link(self, sender_address: str, receiver_address: str) -> None:
        """Return a list of links."""
        try:
            await self._proxy.removeLink(sender_address, receiver_address)
        except BaseHomematicException as ex:
            raise ClientException(
                f"REMOVE_LINK failed with for: {sender_address}/{receiver_address}: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def get_link_peers(self, address: str) -> tuple[str, ...] | None:
        """Return a list of link pers."""
        try:
            return tuple(await self._proxy.getLinkPeers(address))
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_LINK_PEERS failed with for: {address}: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def get_links(self, address: str, flags: int) -> dict[str, Any]:
        """Return a list of links."""
        try:
            return cast(dict[str, Any], await self._proxy.getLinks(address, flags))
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_LINKS failed with for: {address}: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def get_metadata(self, address: str, data_id: str) -> dict[str, Any]:
        """Return the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.getMetadata(address, data_id))
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_METADATA failed with for: {address}/{data_id}: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def set_metadata(
        self, address: str, data_id: str, value: dict[str, Any]
    ) -> dict[str, Any]:
        """Write the metadata for an object."""
        try:
            return cast(dict[str, Any], await self._proxy.setMetadata(address, data_id, value))
        except BaseHomematicException as ex:
            raise ClientException(
                f"SET_METADATA failed with for: {address}/{data_id}/{value}: {reduce_args(args=ex.args)}"
            ) from ex

    @service(log_level=logging.NOTSET)
    async def get_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        call_source: CallSource = CallSource.MANUAL_OR_SCHEDULED,
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
            if paramset_key == ParamsetKey.VALUES:
                return await self._proxy_read.getValue(channel_address, parameter)
            paramset = (
                await self._proxy_read.getParamset(channel_address, ParamsetKey.MASTER) or {}
            )
            return paramset.get(parameter)
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_VALUE failed with for: {channel_address}/{parameter}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @measure_execution_time
    @service()
    async def _set_value(
        self,
        channel_address: str,
        parameter: str,
        value: Any,
        wait_for_callback: int | None,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[ENTITY_KEY]:
        """Set single value on paramset VALUES."""
        try:
            checked_value = (
                self._check_set_value(
                    channel_address=channel_address,
                    paramset_key=ParamsetKey.VALUES,
                    parameter=parameter,
                    value=value,
                )
                if check_against_pd
                else value
            )
            _LOGGER.debug("SET_VALUE: %s, %s, %s", channel_address, parameter, checked_value)
            if rx_mode and (device := self.central.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._proxy.setValue(channel_address, parameter, checked_value, rx_mode)
                else:
                    raise ClientException(f"Unsupported rx_mode: {rx_mode}")
            else:
                await self._proxy.setValue(channel_address, parameter, checked_value)
            # store the send value in the last_value_send_cache
            entity_keys = self._last_value_send_cache.add_set_value(
                channel_address=channel_address, parameter=parameter, value=checked_value
            )
            if wait_for_callback is not None and (
                device := self.central.get_device(
                    address=get_device_address(address=channel_address)
                )
            ):
                await _wait_for_state_change_or_timeout(
                    device=device,
                    entity_keys=entity_keys,
                    values={parameter: checked_value},
                    wait_for_callback=wait_for_callback,
                )
            return entity_keys  # noqa: TRY300
        except BaseHomematicException as ex:
            raise ClientException(
                f"SET_VALUE failed for {channel_address}/{parameter}/{value}: {reduce_args(args=ex.args)}"
            ) from ex

    def _check_set_value(
        self, channel_address: str, paramset_key: ParamsetKey, parameter: str, value: Any
    ) -> Any:
        """Check set_value."""
        return self._convert_value(
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            value=value,
            operation=Operations.WRITE,
        )

    async def set_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        wait_for_callback: int | None = WAIT_FOR_CALLBACK,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[ENTITY_KEY]:
        """Set single value on paramset VALUES."""
        if paramset_key == ParamsetKey.VALUES:
            return await self._set_value(  # type: ignore[no-any-return]
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                wait_for_callback=wait_for_callback,
                rx_mode=rx_mode,
                check_against_pd=check_against_pd,
            )
        return await self.put_paramset(  # type: ignore[no-any-return]
            channel_address=channel_address,
            paramset_key=paramset_key,
            values={parameter: value},
            wait_for_callback=wait_for_callback,
            rx_mode=rx_mode,
            check_against_pd=check_against_pd,
        )

    @service()
    async def get_paramset(self, address: str, paramset_key: ParamsetKey | str) -> dict[str, Any]:
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
            return await self._proxy_read.getParamset(address, paramset_key)  # type: ignore[no-any-return]
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_PARAMSET failed with for {address}/{paramset_key}: {reduce_args(args=ex.args)}"
            ) from ex

    @measure_execution_time
    @service()
    async def put_paramset(
        self,
        channel_address: str,
        paramset_key: ParamsetKey | str,
        values: dict[str, Any],
        wait_for_callback: int | None = WAIT_FOR_CALLBACK,
        rx_mode: CommandRxMode | None = None,
        check_against_pd: bool = False,
    ) -> set[ENTITY_KEY]:
        """
        Set paramsets manually.

        Address is usually the channel_address, but for bidcos devices there is a master paramset at the device.
        Paramset_key can be a str with a channel address in case of manipulating a direct link.
        If paramset_key is string and contains a channel address, then the LINK paramset must be used for a check.
        """
        is_link_call: bool = False
        checked_values = values
        try:
            if check_against_pd:
                check_paramset_key = (
                    ParamsetKey(paramset_key)
                    if is_paramset_key(paramset_key=paramset_key)
                    else ParamsetKey.LINK
                    if (is_link_call := is_channel_address(address=paramset_key))
                    else None
                )
                if check_paramset_key:
                    checked_values = self._check_put_paramset(
                        channel_address=channel_address,
                        paramset_key=check_paramset_key,
                        values=values,
                    )
                else:
                    raise ClientException(
                        "Parameter paramset_key is neither a valid ParamsetKey nor a channel address."
                    )

            _LOGGER.debug(
                "PUT_PARAMSET: %s, %s, %s", channel_address, paramset_key, checked_values
            )
            if rx_mode and (device := self.central.get_device(address=channel_address)):
                if supports_rx_mode(command_rx_mode=rx_mode, rx_modes=device.rx_modes):
                    await self._proxy.putParamset(
                        channel_address, paramset_key, checked_values, rx_mode
                    )
                else:
                    raise ClientException(f"Unsupported rx_mode: {rx_mode}")
            else:
                await self._proxy.putParamset(channel_address, paramset_key, checked_values)

            # if a call is related to a link then no further action is needed
            if is_link_call:
                return set()

            # store the send value in the last_value_send_cache
            entity_keys = self._last_value_send_cache.add_put_paramset(
                channel_address=channel_address,
                paramset_key=ParamsetKey(paramset_key),
                values=checked_values,
            )
            if wait_for_callback is not None and (
                device := self.central.get_device(
                    address=get_device_address(address=channel_address)
                )
            ):
                await _wait_for_state_change_or_timeout(
                    device=device,
                    entity_keys=entity_keys,
                    values=checked_values,
                    wait_for_callback=wait_for_callback,
                )
            return entity_keys  # noqa: TRY300
        except BaseHomematicException as ex:
            raise ClientException(
                f"PUT_PARAMSET failed for {channel_address}/{paramset_key}/{values}: {reduce_args(args=ex.args)}"
            ) from ex

    def _check_put_paramset(
        self, channel_address: str, paramset_key: ParamsetKey, values: dict[str, Any]
    ) -> dict[str, Any]:
        """Check put_paramset."""
        checked_values: dict[str, Any] = {}
        for param, value in values.items():
            checked_values[param] = self._convert_value(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=param,
                value=value,
                operation=Operations.WRITE,
            )
        return checked_values

    def _convert_value(
        self,
        channel_address: str,
        paramset_key: ParamsetKey,
        parameter: str,
        value: Any,
        operation: Operations,
    ) -> Any:
        # Rewrite check for LINK paramset
        """Check a single parameter against paramset descriptions."""
        if parameter_data := self.central.paramset_descriptions.get_parameter_data(
            interface_id=self.interface_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            pd_type = parameter_data["TYPE"]
            pd_value_list = (
                tuple(parameter_data["VALUE_LIST"]) if parameter_data.get("VALUE_LIST") else None
            )
            if (
                not bool(pd_operation := int(parameter_data["OPERATIONS"]) & operation)
                and pd_operation
            ):
                raise ClientException(
                    f"Parameter {parameter} does not support the requested operation {operation.value}"
                )

            return convert_value(value=value, target_type=pd_type, value_list=pd_value_list)
        raise ClientException(
            f"Parameter {parameter} could not be found: {self.interface_id}/{channel_address}/{paramset_key}"
        )

    async def fetch_paramset_description(
        self, channel_address: str, paramset_key: ParamsetKey
    ) -> None:
        """Fetch a specific paramset and add it to the known ones."""
        _LOGGER.debug("FETCH_PARAMSET_DESCRIPTION: %s for %s", paramset_key, channel_address)

        if paramset_description := await self._get_paramset_description(
            address=channel_address, paramset_key=paramset_key
        ):
            self.central.paramset_descriptions.add(
                interface_id=self.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
                paramset_description=paramset_description,
            )

    async def fetch_paramset_descriptions(self, device_description: DeviceDescription) -> None:
        """Fetch paramsets for provided device description."""
        data = await self.get_paramset_descriptions(device_description=device_description)
        for address, paramsets in data.items():
            _LOGGER.debug("FETCH_PARAMSET_DESCRIPTIONS for %s", address)
            for paramset_key, paramset_description in paramsets.items():
                self.central.paramset_descriptions.add(
                    interface_id=self.interface_id,
                    channel_address=address,
                    paramset_key=ParamsetKey(paramset_key),
                    paramset_description=paramset_description,
                )

    async def get_paramset_descriptions(
        self, device_description: DeviceDescription
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get paramsets for provided device description."""
        paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        address = device_description["ADDRESS"]
        paramsets[address] = {}
        _LOGGER.debug("GET_PARAMSET_DESCRIPTIONS for %s", address)
        for p_key in device_description["PARAMSETS"]:
            paramset_key = ParamsetKey(p_key)
            if paramset_description := await self._get_paramset_description(
                address=address, paramset_key=paramset_key
            ):
                paramsets[address][paramset_key] = paramset_description
        return paramsets

    async def _get_paramset_description(
        self, address: str, paramset_key: ParamsetKey
    ) -> dict[str, ParameterData] | None:
        """Get paramset description from CCU."""
        try:
            return cast(
                dict[str, ParameterData],
                await self._proxy_read.getParamsetDescription(address, paramset_key),
            )
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "GET_PARAMSET_DESCRIPTIONS failed with %s [%s] for %s address %s",
                ex.name,
                reduce_args(args=ex.args),
                paramset_key,
                address,
            )
        return None

    async def get_all_paramset_descriptions(
        self, device_descriptions: tuple[DeviceDescription, ...]
    ) -> dict[str, dict[ParamsetKey, dict[str, ParameterData]]]:
        """Get all paramset descriptions for provided device descriptions."""
        all_paramsets: dict[str, dict[ParamsetKey, dict[str, ParameterData]]] = {}
        for device_description in device_descriptions:
            all_paramsets.update(
                await self.get_paramset_descriptions(device_description=device_description)
            )
        return all_paramsets

    @service()
    async def has_program_ids(self, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return False

    @service()
    async def report_value_usage(self, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        return False

    @service()
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
                    if device.product_group in (ProductGroup.HMIPW, ProductGroup.HMIP)
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
            except BaseHomematicException as ex:
                raise ClientException(
                    f"UPDATE_DEVICE_FIRMWARE failed]: {reduce_args(args=ex.args)}"
                ) from ex
            return result
        return False

    async def update_paramset_descriptions(self, device_address: str) -> None:
        """Update paramsets descriptions for provided device_address."""
        if not self.central.device_descriptions.get_device_descriptions(
            interface_id=self.interface_id
        ):
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: "
                "Interface missing in central cache. "
                "Not updating paramsets for %s",
                device_address,
            )
            return

        if device_description := self.central.device_descriptions.find_device_description(
            interface_id=self.interface_id, device_address=device_address
        ):
            await self.fetch_paramset_descriptions(device_description=device_description)
        else:
            _LOGGER.warning(
                "UPDATE_PARAMSET_DESCRIPTIONS failed: "
                "Channel missing in central.cache. "
                "Not updating paramsets for %s",
                device_address,
            )
            return
        await self.central.save_caches(save_paramset_descriptions=True)

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"interface_id: {self.interface_id}"


class ClientCCU(Client):
    """Client implementation for CCU backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        return Backend.CCU

    @property
    def supports_ping_pong(self) -> bool:
        """Return the supports_ping_pong info of the backend."""
        return True

    @measure_execution_time
    async def fetch_device_details(self) -> None:
        """Get all names via JSON-RPS and store in data.NAMES."""
        if json_result := await self._json_rpc_client.get_device_details():
            for device in json_result:
                device_address = device[_JSON_ADDRESS]
                self.central.device_details.add_name(
                    address=device_address, name=device[_JSON_NAME]
                )
                self.central.device_details.add_address_id(
                    address=device_address, hmid=device[_JSON_ID]
                )
                for channel in device.get(_JSON_CHANNELS, []):
                    channel_address = channel[_JSON_ADDRESS]
                    self.central.device_details.add_name(
                        address=channel_address, name=channel[_JSON_NAME]
                    )
                    self.central.device_details.add_address_id(
                        address=channel_address, hmid=channel[_JSON_ID]
                    )
                self.central.device_details.add_interface(
                    address=device_address, interface=device[_JSON_INTERFACE]
                )
        else:
            _LOGGER.debug("FETCH_DEVICE_DETAILS: Unable to fetch device details via JSON-RPC")

    @measure_execution_time
    async def fetch_all_device_data(self) -> None:
        """Fetch all device data from CCU."""
        if all_device_data := await self._json_rpc_client.get_all_device_data(
            interface=self.interface
        ):
            _LOGGER.debug(
                "FETCH_ALL_DEVICE_DATA: Fetched all device data for interface %s", self.interface
            )
            self.central.data_cache.add_data(all_device_data=all_device_data)
        else:
            _LOGGER.debug(
                "FETCH_ALL_DEVICE_DATA: Unable to get all device data via JSON-RPC RegaScript for interface %s",
                self.interface,
            )

    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Check if _proxy is still initialized."""
        try:
            dt_now = datetime.now()
            if handle_ping_pong and self.supports_ping_pong:
                self._ping_pong_cache.handle_send_ping(ping_ts=dt_now)
            calllerId = (
                f"{self.interface_id}#{dt_now.strftime(format=DATETIME_FORMAT_MILLIS)}"
                if handle_ping_pong
                else self.interface_id
            )
            await self._proxy.ping(calllerId)
            self.modified_at = dt_now
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @service()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU."""
        return await self._json_rpc_client.execute_program(pid=pid)

    @service()
    async def has_program_ids(self, channel_hmid: str) -> bool:
        """Return if a channel has program ids."""
        return await self._json_rpc_client.has_program_ids(channel_hmid=channel_hmid)

    @service()
    async def report_value_usage(self, address: str, value_id: str, ref_counter: int) -> bool:
        """Report value usage."""
        try:
            return bool(await self._proxy.reportValueUsage(address, value_id, ref_counter))
        except BaseHomematicException as ex:
            raise ClientException(
                f"REPORT_VALUE_USAGE failed with: {address}/{value_id}/{ref_counter}: {reduce_args(args=ex.args)}"
            ) from ex

    @measure_execution_time
    @service()
    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        return await self._json_rpc_client.set_system_variable(name=name, value=value)

    @service()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        return await self._json_rpc_client.delete_system_variable(name=name)

    @service()
    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        return await self._json_rpc_client.get_system_variable(name=name)

    @service()
    async def get_all_system_variables(
        self, include_internal: bool
    ) -> tuple[SystemVariableData, ...]:
        """Get all system variables from CCU / Homegear."""
        return await self._json_rpc_client.get_all_system_variables(
            include_internal=include_internal
        )

    async def get_all_programs(self, include_internal: bool) -> tuple[ProgramData, ...]:
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
        return await self._json_rpc_client.get_system_information()


class ClientHomegear(Client):
    """Client implementation for Homegear backend."""

    @property
    def model(self) -> str:
        """Return the model of the backend."""
        if self._config.version:
            return (
                Backend.PYDEVCCU
                if Backend.PYDEVCCU.lower() in self._config.version
                else Backend.HOMEGEAR
            )
        return Backend.CCU

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
                    await self._proxy_read.getMetadata(address, _NAME),
                )
            except BaseHomematicException as ex:
                _LOGGER.warning(
                    "%s [%s] Failed to fetch name for device %s",
                    ex.name,
                    reduce_args(args=ex.args),
                    address,
                )

    async def check_connection_availability(self, handle_ping_pong: bool) -> bool:
        """Check if proxy is still initialized."""
        try:
            await self._proxy.clientServerInitialized(self.interface_id)
            self.modified_at = datetime.now()
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "CHECK_CONNECTION_AVAILABILITY failed: %s [%s]",
                ex.name,
                reduce_args(args=ex.args),
            )
        else:
            return True
        self.modified_at = INIT_DATETIME
        return False

    @service()
    async def execute_program(self, pid: str) -> bool:
        """Execute a program on Homegear."""
        return True

    @measure_execution_time
    @service()
    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""
        try:
            await self._proxy.setSystemVariable(name, value)
        except BaseHomematicException as ex:
            raise ClientException(
                f"SET_SYSTEM_VARIABLE failed: {reduce_args(args=ex.args)}"
            ) from ex
        return True

    @service()
    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        try:
            await self._proxy.deleteSystemVariable(name)
        except BaseHomematicException as ex:
            raise ClientException(
                f"DELETE_SYSTEM_VARIABLE failed: {reduce_args(args=ex.args)}"
            ) from ex
        return True

    @service()
    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        try:
            return await self._proxy.getSystemVariable(name)
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_SYSTEM_VARIABLE failed: {reduce_args(args=ex.args)}"
            ) from ex

    @service()
    async def get_all_system_variables(
        self, include_internal: bool
    ) -> tuple[SystemVariableData, ...]:
        """Get all system variables from CCU / Homegear."""
        variables: list[SystemVariableData] = []
        try:
            if hg_variables := await self._proxy.getAllSystemVariables():
                for name, value in hg_variables.items():
                    variables.append(SystemVariableData(name=name, value=value))
        except BaseHomematicException as ex:
            raise ClientException(
                f"GET_ALL_SYSTEM_VARIABLES failed: {reduce_args(args=ex.args)}"
            ) from ex
        return tuple(variables)

    async def get_all_programs(self, include_internal: bool) -> tuple[ProgramData, ...]:
        """Get all programs, if available."""
        return ()

    async def get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms from Homegear."""
        return {}

    async def get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions from Homegear."""
        return {}

    async def _get_system_information(self) -> SystemInformation:
        """Get system information of the backend."""
        return SystemInformation(
            available_interfaces=(InterfaceName.BIDCOS_RF,), serial=HOMEGEAR_SERIAL
        )


class _ClientConfig:
    """Config for a Client."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        interface_config: InterfaceConfig,
    ) -> None:
        self.central: Final = central
        self.version: str = "0"
        self.system_information = SystemInformation()
        self.interface_config: Final = interface_config
        self.interface: Final = interface_config.interface
        self.interface_id: Final = interface_config.interface_id
        self.max_read_workers: Final[int] = central.config.max_read_workers
        self.has_credentials: Final[bool] = (
            central.config.username is not None and central.config.password is not None
        )
        self.init_url: Final[str] = f"http://{central.config.callback_host
            if central.config.callback_host
            else central.callback_ip_addr}:{central.config.callback_port
            if central.config.callback_port
            else central.listen_port}"
        self.xml_rpc_uri: Final = build_xml_rpc_uri(
            host=central.config.host,
            port=interface_config.port,
            path=interface_config.remote_path,
            tls=central.config.tls,
        )

    async def get_client(self) -> Client:
        """Identify the used client."""
        client: Client | None = None
        check_proxy = await self._get_simple_xml_rpc_proxy()
        try:
            if methods := check_proxy.supported_methods:
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
                if await client.check_connection_availability(handle_ping_pong=False):
                    return client
            raise NoConnection(f"No connection to {self.interface_id}")
        except BaseHomematicException:
            raise
        except Exception as ex:
            raise NoConnection(f"Unable to connect {reduce_args(args=ex.args)}.") from ex

    async def get_xml_rpc_proxy(
        self, auth_enabled: bool | None = None, max_workers: int = DEFAULT_MAX_WORKERS
    ) -> XmlRpcProxy:
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
        xml_proxy = XmlRpcProxy(
            max_workers=max_workers,
            interface_id=self.interface_id,
            connection_state=central_config.connection_state,
            uri=self.xml_rpc_uri,
            headers=xml_rpc_headers,
            tls=central_config.tls,
            verify_tls=central_config.verify_tls,
        )
        await xml_proxy.do_init()
        return xml_proxy

    async def _get_simple_xml_rpc_proxy(self) -> XmlRpcProxy:
        """Return a XmlRPC proxy for backend communication."""
        return await self.get_xml_rpc_proxy(auth_enabled=True, max_workers=0)


class InterfaceConfig:
    """interface config for a Client."""

    def __init__(
        self,
        central_name: str,
        interface: InterfaceName,
        port: int,
        remote_path: str | None = None,
    ) -> None:
        """Init the interface config."""
        self.interface: Final[InterfaceName] = interface
        self.interface_id: Final[str] = f"{central_name}-{self.interface}"
        self.port: Final = port
        self.remote_path: Final = remote_path
        self._init_validate()

    def _init_validate(self) -> None:
        """Validate the client_config."""
        if self.interface not in list(InterfaceName):
            _LOGGER.warning(
                "VALIDATE interface config failed: "
                "Interface names must be within [%s] for production use",
                ", ".join(list(InterfaceName)),
            )


async def create_client(
    central: hmcu.CentralUnit,
    interface_config: InterfaceConfig,
) -> Client:
    """Return a new client for with a given interface_config."""
    return await _ClientConfig(central=central, interface_config=interface_config).get_client()


def get_client(interface_id: str) -> Client | None:
    """Return client by interface_id."""
    for central in hmcu.CENTRAL_INSTANCES.values():
        if central.has_client(interface_id=interface_id):
            return central.get_client(interface_id=interface_id)
    return None


@measure_execution_time
async def _wait_for_state_change_or_timeout(
    device: HmDevice, entity_keys: set[ENTITY_KEY], values: dict[str, Any], wait_for_callback: int
) -> None:
    """Wait for an entity to change state."""
    waits = [
        _track_single_entity_state_change_or_timeout(
            device=device,
            entity_key=entity_key,
            value=values.get(entity_key[1]),
            wait_for_callback=wait_for_callback,
        )
        for entity_key in entity_keys
    ]
    await asyncio.gather(*waits)


@measure_execution_time
async def _track_single_entity_state_change_or_timeout(
    device: HmDevice, entity_key: ENTITY_KEY, value: Any, wait_for_callback: int
) -> None:
    """Wait for an entity to change state."""
    ev = asyncio.Event()

    def _async_event_changed(*args: Any, **kwargs: Any) -> None:
        if entity:
            _LOGGER.debug(
                "TRACK_SINGLE_ENTITY_STATE_CHANGE_OR_TIMEOUT: Received event %s with value %s",
                entity_key,
                entity.value,
            )
            if _isclose(value, entity.value):
                _LOGGER.debug(
                    "TRACK_SINGLE_ENTITY_STATE_CHANGE_OR_TIMEOUT: Finished event %s with value %s",
                    entity_key,
                    entity.value,
                )
                ev.set()

    channel_address, paramset_key, parameter = entity_key
    if entity := device.get_generic_entity(
        channel_address=channel_address,
        parameter=parameter,
        paramset_key=ParamsetKey(paramset_key),
    ):
        if not entity.supports_events:
            _LOGGER.debug(
                "TRACK_SINGLE_ENTITY_STATE_CHANGE_OR_TIMEOUT: Entity supports no events %s",
                entity_key,
            )
            return
        if (
            unsub := entity.register_entity_updated_callback(
                cb=_async_event_changed, custom_id=DEFAULT_CUSTOM_ID
            )
        ) is None:
            return

        try:
            async with asyncio.timeout(wait_for_callback):
                await ev.wait()
        except TimeoutError:
            _LOGGER.debug(
                "TRACK_SINGLE_ENTITY_STATE_CHANGE_OR_TIMEOUT: Timeout waiting for event %s with value %s",
                entity_key,
                entity.value,
            )
        finally:
            unsub()


def _isclose(value1: Any, value2: Any) -> bool:
    """Check if the both values are close to each other."""
    if isinstance(value1, float):
        return bool(round(value1, 2) == round(value2, 2))
    return bool(value1 == value2)
