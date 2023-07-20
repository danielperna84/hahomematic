"""Module for the Device class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Final

from hahomematic import central_unit as hmcu, exporter as hmexp
from hahomematic.const import (
    ENTITY_EVENTS,
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    HM_AVAILABLE_FIRMWARE,
    HM_FIRMWARE,
    HM_FIRMWARE_UPDATABLE,
    HM_FIRMWARE_UPDATE_STATE,
    HM_SUBTYPE,
    HM_TYPE,
    HM_VIRTUAL_REMOTE_TYPES,
    IDENTIFIER_SEPARATOR,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    PARAMSET_KEY_MASTER,
    PARAMSET_KEY_VALUES,
    RELEVANT_INIT_PARAMETERS,
    HmCallSource,
    HmDeviceFirmwareState,
    HmEventType,
    HmForcedDeviceAvailability,
    HmInterface,
    HmProductGroup,
)
from hahomematic.exceptions import BaseHomematicException
from hahomematic.platforms import custom as cep
from hahomematic.platforms.custom import entity as hmce
from hahomematic.platforms.entity import BaseEntity, CallbackEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.support import (
    PayloadMixin,
    config_property,
    get_device_name,
    value_property,
)
from hahomematic.platforms.update import HmUpdate
from hahomematic.support import updated_within_seconds

_LOGGER = logging.getLogger(__name__)


class HmDevice(PayloadMixin):
    """Object to hold information about a device and associated entities."""

    def __init__(self, central: hmcu.CentralUnit, interface_id: str, device_address: str) -> None:
        """Initialize the device object."""
        PayloadMixin.__init__(self)
        self.central: Final = central
        self._attr_interface_id: Final = interface_id
        self._attr_interface: Final = central.device_details.get_interface(device_address)
        self.client: Final = central.get_client(interface_id=interface_id)
        self._attr_device_address: Final = device_address
        self.channels: Final = central.device_descriptions.get_channels(
            interface_id, device_address
        )
        _LOGGER.debug(
            "__INIT__: Initializing device: %s, %s",
            interface_id,
            device_address,
        )
        self.custom_entities: Final[dict[str, hmce.CustomEntity]] = {}
        self.generic_entities: Final[dict[tuple[str, str], GenericEntity]] = {}
        self.generic_events: Final[dict[tuple[str, str], GenericEvent]] = {}
        self.wrapper_entities: Final[dict[tuple[str, str], WrapperEntity]] = {}
        self._attr_last_update: datetime = INIT_DATETIME
        self._forced_availability: HmForcedDeviceAvailability = HmForcedDeviceAvailability.NOT_SET
        self._update_callbacks: Final[list[Callable]] = []
        self._firmware_update_callbacks: Final[list[Callable]] = []
        self._attr_device_type: Final = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HM_TYPE,
            )
        )
        self._attr_sub_type: Final = str(
            central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HM_SUBTYPE,
            )
        )
        self._attr_product_group: Final = self._identify_product_group()
        # marker if device will be created as custom entity
        self._has_custom_entity_definition: Final = cep.has_custom_entity_definition_by_device(
            device=self
        )

        self._attr_name: Final = get_device_name(
            central=central,
            device_address=device_address,
            device_type=self._attr_device_type,
        )
        self.value_cache: Final = ValueCache(device=self)
        self._attr_room: Final = central.device_details.get_room(device_address=device_address)
        self._update_firmware_data()
        self._attr_update_entity: Final = (
            HmUpdate(device=self) if self.device_type not in HM_VIRTUAL_REMOTE_TYPES else None
        )
        _LOGGER.debug(
            "__INIT__: Initialized device: %s, %s, %s, %s",
            self._attr_interface_id,
            self._attr_device_address,
            self._attr_device_type,
            self._attr_name,
        )

    def _update_firmware_data(self) -> None:
        """Update firmware related data from device descriptions."""
        self._attr_available_firmware: str | None = (
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._attr_interface_id,
                device_address=self._attr_device_address,
                parameter=HM_AVAILABLE_FIRMWARE,
            )
            or None
        )
        self._attr_firmware = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._attr_interface_id,
                device_address=self._attr_device_address,
                parameter=HM_FIRMWARE,
            )
        )

        try:
            self._attr_firmware_update_state = HmDeviceFirmwareState(
                str(
                    self.central.device_descriptions.get_device_parameter(
                        interface_id=self._attr_interface_id,
                        device_address=self._attr_device_address,
                        parameter=HM_FIRMWARE_UPDATE_STATE,
                    )
                )
            )
        except ValueError:
            self._attr_firmware_update_state = HmDeviceFirmwareState.UP_TO_DATE

        self._attr_firmware_updatable = bool(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._attr_interface_id,
                device_address=self._attr_device_address,
                parameter=HM_FIRMWARE_UPDATABLE,
            )
        )

    def _identify_product_group(self) -> HmProductGroup:
        """Identify the product group of the homematic device."""
        if self.interface == HmInterface.HMIP:
            l_device_type = self.device_type.lower()
            if l_device_type.startswith("hmipw"):
                return HmProductGroup.HMIPW
            if l_device_type.startswith("hmip"):
                return HmProductGroup.HMIP
        if self.interface == HmInterface.HMW:
            return HmProductGroup.HMW
        if self.interface == HmInterface.HM:
            return HmProductGroup.HM
        if self.interface == HmInterface.VIRTUAL:
            return HmProductGroup.VIRTUAL
        return HmProductGroup.UNKNOWN

    @value_property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._forced_availability != HmForcedDeviceAvailability.NOT_SET:
            return self._forced_availability == HmForcedDeviceAvailability.FORCE_TRUE
        un_reach = self._e_unreach
        if un_reach is None:
            un_reach = self._e_sticky_un_reach
        if un_reach is not None and un_reach.value is not None:
            return not un_reach.value
        return True

    @config_property
    def available_firmware(self) -> str | None:
        """Return the available firmware of the device."""
        return self._attr_available_firmware

    @property
    def config_pending(self) -> bool:
        """Return if a config change of the device is pending."""
        if self._e_config_pending is not None and self._e_config_pending.value is not None:
            return self._e_config_pending.value is True
        return False

    @config_property
    def device_address(self) -> str:
        """Return the device_address of the device."""
        return self._attr_device_address

    @config_property
    def device_type(self) -> str:
        """Return the device_type of the device."""
        return self._attr_device_type

    @config_property
    def firmware(self) -> str:
        """Return the firmware of the device."""
        return self._attr_firmware

    @config_property
    def firmware_updatable(self) -> bool:
        """Return the firmware update state of the device."""
        return self._attr_firmware_updatable

    @config_property
    def firmware_update_state(self) -> HmDeviceFirmwareState:
        """Return the firmware update state of the device."""
        return self._attr_firmware_update_state

    @config_property
    def identifier(self) -> str:
        """Return the identifier of the device."""
        return f"{self._attr_device_address}{IDENTIFIER_SEPARATOR}{self._attr_interface_id}"

    @config_property
    def interface(self) -> str:
        """Return the interface of the device."""
        return self._attr_interface

    @config_property
    def interface_id(self) -> str:
        """Return the interface_id of the device."""
        return self._attr_interface_id

    @property
    def has_custom_entity_definition(self) -> bool:
        """Return if custom_entity definition is available for the device."""
        return self._has_custom_entity_definition

    @config_property
    def name(self) -> str:
        """Return the name of the device."""
        return self._attr_name

    @config_property
    def product_group(self) -> HmProductGroup:
        """Return the product group of the device."""
        return self._attr_product_group

    @config_property
    def room(self) -> str | None:
        """Return the room of the device."""
        return self._attr_room

    @config_property
    def sub_type(self) -> str:
        """Return the sub_type of the device."""
        return self._attr_sub_type

    @property
    def update_entity(self) -> HmUpdate | None:
        """Return the device firmware update entity of the device."""
        return self._attr_update_entity

    @property
    def _e_unreach(self) -> GenericEntity | None:
        """Return th UNREACH entity."""
        return self.generic_entities.get((f"{self._attr_device_address}:0", EVENT_UN_REACH))

    @property
    def _e_sticky_un_reach(self) -> GenericEntity | None:
        """Return th STICKY_UN_REACH entity."""
        return self.generic_entities.get((f"{self._attr_device_address}:0", EVENT_STICKY_UN_REACH))

    @property
    def _e_config_pending(self) -> GenericEntity | None:
        """Return th CONFIG_PENDING entity."""
        return self.generic_entities.get((f"{self._attr_device_address}:0", EVENT_CONFIG_PENDING))

    def add_entity(self, entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(entity, BaseEntity):
            self.central.add_entity(entity=entity)
        if isinstance(entity, GenericEntity):
            self.generic_entities[(entity.channel_address, entity.parameter)] = entity
            self.register_update_callback(entity.update_entity)
        if isinstance(entity, WrapperEntity):
            self.wrapper_entities[(entity.channel_address, entity.parameter)] = entity
            self.register_update_callback(entity.update_entity)
        if isinstance(entity, hmce.CustomEntity):
            self.custom_entities[entity.unique_identifier] = entity
        if isinstance(entity, GenericEvent):
            self.generic_events[(entity.channel_address, entity.parameter)] = entity

    def remove_entity(self, entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(entity, BaseEntity):
            self.central.remove_entity(entity=entity)
        if isinstance(entity, GenericEntity):
            del self.generic_entities[(entity.channel_address, entity.parameter)]
            self.unregister_update_callback(entity.update_entity)
        if isinstance(entity, WrapperEntity):
            del self.wrapper_entities[(entity.channel_address, entity.parameter)]
            self.unregister_update_callback(entity.update_entity)
        if isinstance(entity, hmce.CustomEntity):
            del self.custom_entities[entity.unique_identifier]
        if isinstance(entity, GenericEvent):
            del self.generic_events[(entity.channel_address, entity.parameter)]
        entity.remove_entity()

    def clear_collections(self) -> None:
        """Remove entities from collections and central."""
        for event in list(self.generic_events.values()):
            self.remove_entity(event)
        self.generic_events.clear()

        for entity in list(self.generic_entities.values()):
            self.remove_entity(entity)
        self.generic_entities.clear()

        for custom_entity in list(self.custom_entities.values()):
            self.remove_entity(custom_entity)
        self.custom_entities.clear()

        for wrapper_entity in list(self.wrapper_entities.values()):
            self.remove_entity(wrapper_entity)
        self.wrapper_entities.clear()

        self.generic_events.clear()

    def register_update_callback(self, update_callback: Callable) -> None:
        """Register update callback."""
        if callable(update_callback) and update_callback not in self._update_callbacks:
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """Remove update callback."""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def register_firmware_update_callback(self, firmware_update_callback: Callable) -> None:
        """Register firmware update callback."""
        if (
            callable(firmware_update_callback)
            and firmware_update_callback not in self._firmware_update_callbacks
        ):
            self._firmware_update_callbacks.append(firmware_update_callback)

    def unregister_firmware_update_callback(self, firmware_update_callback: Callable) -> None:
        """Remove firmware update callback."""
        if firmware_update_callback in self._firmware_update_callbacks:
            self._firmware_update_callbacks.remove(firmware_update_callback)

    def _set_last_update(self) -> None:
        self._attr_last_update = datetime.now()

    def get_all_entities(self) -> list[hmce.CustomEntity | GenericEntity | WrapperEntity]:
        """Return all entities of a device."""
        all_entities: list[hmce.CustomEntity | GenericEntity | WrapperEntity] = []
        all_entities.extend(self.custom_entities.values())
        all_entities.extend(self.generic_entities.values())
        all_entities.extend(self.wrapper_entities.values())
        return all_entities

    def get_channel_events(self, event_type: HmEventType) -> dict[int, list[GenericEvent]]:
        """Return a list of specific events of a channel."""
        event_dict: dict[int, list[GenericEvent]] = {}
        if event_type not in ENTITY_EVENTS:
            return event_dict
        for event in self.generic_events.values():
            if event.event_type == event_type and event.channel_no is not None:
                if event.channel_no not in event_dict:
                    event_dict[event.channel_no] = []
                event_dict[event.channel_no].append(event)

        return event_dict

    def get_generic_entity(self, channel_address: str, parameter: str) -> GenericEntity | None:
        """Return an entity from device."""
        return self.generic_entities.get((channel_address, parameter))

    def get_generic_event(self, channel_address: str, parameter: str) -> GenericEvent | None:
        """Return a generic event from device."""
        return self.generic_events.get((channel_address, parameter))

    def set_forced_availability(self, forced_availability: HmForcedDeviceAvailability) -> None:
        """Set the availability of the device."""
        if self._forced_availability != forced_availability:
            self._forced_availability = forced_availability
            for entity in self.generic_entities.values():
                entity.update_entity()

    async def export_device_definition(self) -> None:
        """Export the device definition for current device."""
        await hmexp.save_device_definition(
            client=self.client,
            interface_id=self._attr_interface_id,
            device_address=self._attr_device_address,
        )

    def refresh_firmware_data(self) -> None:
        """Refresh firmware data of the device."""
        old_available_firmware = self._attr_available_firmware
        old_firmware = self._attr_firmware
        old_firmware_update_state = self._attr_firmware_update_state
        old_firmware_updatable = self._attr_firmware_updatable

        self._update_firmware_data()

        if (
            old_available_firmware != self._attr_available_firmware
            or old_firmware != self._attr_firmware
            or old_firmware_update_state != self._attr_firmware_update_state
            or old_firmware_updatable != self._attr_firmware_updatable
        ):
            for _firmware_callback in self._firmware_update_callbacks:
                _firmware_callback()

    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Update the firmware of the homematic device."""
        update_result = await self.client.update_device_firmware(
            device_address=self._attr_device_address
        )

        async def refresh_data() -> None:
            for refresh_interval in refresh_after_update_intervals:
                await asyncio.sleep(refresh_interval)
                await self.central.refresh_firmware_data(device_address=self._attr_device_address)

        if refresh_after_update_intervals:
            self.central.create_task(target=refresh_data(), name="refresh_firmware_data")

        return update_result

    async def load_value_cache(self) -> None:
        """Init the parameter cache."""
        if len(self.generic_entities) > 0:
            await self.value_cache.init_base_entities()
        if len(self.generic_events) > 0:
            await self.value_cache.init_readable_events()
        _LOGGER.debug(
            "INIT_DATA: Skipping load_data, missing entities for %s",
            self._attr_device_address,
        )

    async def reload_paramset_descriptions(self) -> None:
        """Reload paramset for device."""
        for (
            paramset_key,
            channel_addresses,
        ) in self.central.paramset_descriptions.get_channel_addresses_by_paramset_key(
            interface_id=self._attr_interface_id,
            device_address=self._attr_device_address,
        ).items():
            for channel_address in channel_addresses:
                await self.client.fetch_paramset_description(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    save_to_file=False,
                )
        await self.central.paramset_descriptions.save()
        for entity in self.generic_entities.values():
            entity.update_parameter_data()
        self.update_device()

    def update_device(self, *args: Any) -> None:
        """Do what is needed when the state of the entity has been updated."""
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(*args)

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address: {self._attr_device_address}, "
            f"type: {len(self._attr_device_type)}, "
            f"name: {self._attr_name}, "
            f"generic_entities: {len(self.generic_entities)}, "
            f"custom_entities: {len(self.custom_entities)}, "
            f"wrapper_entities: {len(self.wrapper_entities)}, "
            f"events: {len(self.generic_events)}"
        )


class ValueCache:
    """A Cache to temporaily stored values."""

    _NO_VALUE_CACHE_ENTRY: Final = "NO_VALUE_CACHE_ENTRY"

    _sema_get_or_load_value: Final = asyncio.BoundedSemaphore(1)

    def __init__(self, device: HmDevice) -> None:
        """Init the value cache."""
        self._attr_device: Final = device
        # { parparamset_key, {channel_address, {parameter, CacheEntry}}}
        self._attr_value_cache: Final[dict[str, dict[str, dict[str, CacheEntry]]]] = {}

    async def init_base_entities(self) -> None:
        """Load data by get_value."""
        try:
            for entity in self._get_base_entities():
                value = await self.get_value(
                    channel_address=entity.channel_address,
                    paramset_key=entity.paramset_key,
                    parameter=entity.parameter,
                    call_source=HmCallSource.HM_INIT,
                )
                entity.update_value(value=value)
        except BaseHomematicException as bhe:
            _LOGGER.debug(
                "init_base_entities: Failed to init cache for channel0 %s, %s [%s]",
                self._attr_device.device_type,
                self._attr_device.device_address,
                bhe,
            )

    def _get_base_entities(self) -> set[GenericEntity]:
        """Get entities of channel 0 and master."""
        entities: list[GenericEntity] = []
        for entity in self._attr_device.generic_entities.values():
            if (
                entity.channel_no == 0
                and entity.paramset_key == PARAMSET_KEY_VALUES
                and entity.parameter in RELEVANT_INIT_PARAMETERS
            ) or entity.paramset_key == PARAMSET_KEY_MASTER:
                entities.append(entity)
        return set(entities)

    async def init_readable_events(self) -> None:
        """Load data by get_value."""
        try:
            for event in self._get_readable_events():
                value = await self.get_value(
                    channel_address=event.channel_address,
                    paramset_key=event.paramset_key,
                    parameter=event.parameter,
                    call_source=HmCallSource.HM_INIT,
                )
                event.update_value(value=value)
        except BaseHomematicException as bhe:
            _LOGGER.debug(
                "init_base_events: Failed to init cache for channel0 %s, %s [%s]",
                self._attr_device.device_type,
                self._attr_device.device_address,
                bhe,
            )

    def _get_readable_events(self) -> set[GenericEvent]:
        """Get readable events."""
        events: list[GenericEvent] = []
        for event in self._attr_device.generic_events.values():
            if event.is_readable:
                events.append(event)
        return set(events)

    async def get_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        call_source: HmCallSource,
        max_age_seconds: int = MAX_CACHE_AGE,
    ) -> Any:
        """Load data."""
        async with self._sema_get_or_load_value:
            if (
                cached_value := self._get_value_from_cache(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    max_age_seconds=max_age_seconds,
                )
            ) != NO_CACHE_ENTRY:
                return (
                    NO_CACHE_ENTRY if cached_value == self._NO_VALUE_CACHE_ENTRY else cached_value
                )

            value: Any = self._NO_VALUE_CACHE_ENTRY
            try:
                value = await self._attr_device.client.get_value(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    call_source=call_source,
                )
            except BaseHomematicException as bhe:
                _LOGGER.debug(
                    "GET_OR_LOAD_VALUE: Failed to get data for %s, %s, %s: %s",
                    self._attr_device.device_type,
                    channel_address,
                    parameter,
                    bhe,
                )
            if paramset_key not in self._attr_value_cache:
                self._attr_value_cache[paramset_key] = {}
            if channel_address not in self._attr_value_cache[paramset_key]:
                self._attr_value_cache[paramset_key][channel_address] = {}
            # write value to cache even if an exception has occurred
            # to avoid repetitive calls to CCU within max_age_seconds
            self._attr_value_cache[paramset_key][channel_address][parameter] = CacheEntry(
                value=value, last_update=datetime.now()
            )
            return NO_CACHE_ENTRY if value == self._NO_VALUE_CACHE_ENTRY else value

    def _get_value_from_cache(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        max_age_seconds: int,
    ) -> Any:
        """Load data from caches."""
        # Try to get data from central cache
        if (
            global_value := self._attr_device.central.device_data.get_device_data(
                interface=self._attr_device.interface,
                channel_address=channel_address,
                parameter=parameter,
                max_age_seconds=max_age_seconds,
            )
        ) != NO_CACHE_ENTRY:
            return global_value

        # Try to get data from device cache
        if (
            cache_entry := self._attr_value_cache.get(paramset_key, {})
            .get(channel_address, {})
            .get(
                parameter,
                CacheEntry.empty(),
            )
        ) != CacheEntry.empty() and updated_within_seconds(
            last_update=cache_entry.last_update, max_age_seconds=max_age_seconds
        ):
            return cache_entry.value
        return NO_CACHE_ENTRY


@dataclass
class CacheEntry:
    """An entry for the value cache."""

    value: Any
    last_update: datetime

    @staticmethod
    def empty() -> CacheEntry:
        """Return empty cache entry."""
        return CacheEntry(value=NO_CACHE_ENTRY, last_update=datetime.min)
