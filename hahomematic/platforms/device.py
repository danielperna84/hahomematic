"""Module for the Device class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any, Final

from hahomematic import central_unit as hmcu, client as hmcl, exporter as hm_support
from hahomematic.const import (
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    HM_FIRMWARE,
    HM_SUBTYPE,
    HM_TYPE,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    PARAMSET_KEY_MASTER,
    PARAMSET_KEY_VALUES,
    RELEVANT_INIT_PARAMETERS,
    HmCallSource,
    HmForcedDeviceAvailability,
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
from hahomematic.support import Channel, updated_within_seconds

_LOGGER = logging.getLogger(__name__)


class HmDevice(PayloadMixin):
    """Object to hold information about a device and associated entities."""

    def __init__(self, central: hmcu.CentralUnit, interface_id: str, device_address: str) -> None:
        """Initialize the device object."""
        PayloadMixin.__init__(self)
        self.central: Final[hmcu.CentralUnit] = central
        self._attr_interface_id: Final[str] = interface_id
        self._attr_interface: Final[str] = central.device_details.get_interface(device_address)
        self.client: Final[hmcl.Client] = central.get_client(interface_id=interface_id)
        self._attr_device_address: Final[str] = device_address
        self.channels: Final[dict[str, Channel]] = central.device_descriptions.get_channels(
            interface_id, device_address
        )
        _LOGGER.debug(
            "__INIT__: Initializing device: %s, %s",
            interface_id,
            device_address,
        )
        self.generic_entities: dict[tuple[str, str], GenericEntity] = {}
        self.wrapper_entities: dict[tuple[str, str], WrapperEntity] = {}
        self.custom_entities: dict[str, hmce.CustomEntity] = {}
        self.events: dict[tuple[str, str], GenericEvent] = {}
        self._attr_last_update: datetime = INIT_DATETIME
        self._forced_availability: HmForcedDeviceAvailability = HmForcedDeviceAvailability.NOT_SET
        self._update_callbacks: list[Callable] = []
        self._attr_device_type: Final[str] = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HM_TYPE,
            )
        )
        self._attr_sub_type: Final[str] = str(
            central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HM_SUBTYPE,
            )
        )
        # marker if device will be created as custom entity
        self._has_custom_entity_definition: Final[
            bool
        ] = cep.has_custom_entity_definition_by_device(device=self)
        self._attr_firmware: Final[str] = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HM_FIRMWARE,
            )
        )

        self._attr_name: Final[str] = get_device_name(
            central=central,
            device_address=device_address,
            device_type=self._attr_device_type,
        )
        self.value_cache: Final[ValueCache] = ValueCache(device=self)
        self._attr_room: str | None = central.device_details.get_room(
            device_address=device_address
        )

        _LOGGER.debug(
            "__INIT__: Initialized device: %s, %s, %s, %s",
            self._attr_interface_id,
            self._attr_device_address,
            self._attr_device_type,
            self._attr_name,
        )

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
    def room(self) -> str | None:
        """Return the room of the device."""
        return self._attr_room

    @config_property
    def sub_type(self) -> str:
        """Return the sub_type of the device."""
        return self._attr_sub_type

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
            self.events[(entity.channel_address, entity.parameter)] = entity

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
            del self.events[(entity.channel_address, entity.parameter)]
        entity.remove_entity()

    def clear_collections(self) -> None:
        """Remove entities from collections and central."""
        for event in list(self.events.values()):
            self.remove_entity(event)
        self.events.clear()

        for entity in list(self.generic_entities.values()):
            self.remove_entity(entity)
        self.generic_entities.clear()

        for custom_entity in list(self.custom_entities.values()):
            self.remove_entity(custom_entity)
        self.custom_entities.clear()

        for wrapper_entity in list(self.wrapper_entities.values()):
            self.remove_entity(wrapper_entity)
        self.wrapper_entities.clear()

        self.events.clear()

    def register_update_callback(self, update_callback: Callable) -> None:
        """Register update callback."""
        if callable(update_callback) and update_callback not in self._update_callbacks:
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """Remove update callback."""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def _set_last_update(self) -> None:
        self._attr_last_update = datetime.now()

    def get_generic_entity(self, channel_address: str, parameter: str) -> GenericEntity | None:
        """Return an entity from device."""
        return self.generic_entities.get((channel_address, parameter))

    def set_forced_availability(self, forced_availability: HmForcedDeviceAvailability) -> None:
        """Set the availability of the device."""
        if self._forced_availability != forced_availability:
            self._forced_availability = forced_availability
            for entity in self.generic_entities.values():
                entity.update_entity()

    async def export_device_definition(self) -> None:
        """Export the device definition for current device."""
        await hm_support.save_device_definition(
            client=self.client,
            interface_id=self._attr_interface_id,
            device_address=self._attr_device_address,
        )

    async def load_value_cache(self) -> None:
        """Init the parameter cache."""
        if len(self.generic_entities) > 0:
            await self.value_cache.init_base_entities()
        if len(self.events) > 0:
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
            f"events: {len(self.events)}"
        )


class ValueCache:
    """A Cache to temporaily stored values."""

    _NO_VALUE_CACHE_ENTRY: Final[str] = "NO_VALUE_CACHE_ENTRY"

    _sema_get_or_load_value = asyncio.BoundedSemaphore(1)

    def __init__(self, device: HmDevice) -> None:
        """Init the value cache."""
        self._attr_device: Final[HmDevice] = device
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
        for event in self._attr_device.events.values():
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
