"""Module for the Device class."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Set
from copy import copy
from datetime import datetime
import logging
import os
import random
from typing import Any, Final

import orjson

from hahomematic import central as hmcu
from hahomematic.const import (
    DEFAULT_DEVICE_DESCRIPTIONS_DIR,
    DEFAULT_PARAMSET_DESCRIPTIONS_DIR,
    ENTITY_EVENTS,
    IDENTIFIER_SEPARATOR,
    INIT_DATETIME,
    NO_CACHE_ENTRY,
    PLATFORMS,
    RELEVANT_INIT_PARAMETERS,
    VIRTUAL_REMOTE_TYPES,
    CallSource,
    DataOperationResult,
    Description,
    DeviceFirmwareState,
    EntityUsage,
    EventType,
    ForcedDeviceAvailability,
    HmPlatform,
    Manufacturer,
    Parameter,
    ParamsetKey,
    ProductGroup,
)
from hahomematic.exceptions import BaseHomematicException
from hahomematic.platforms.custom import definition as hmed, entity as hmce
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.entity import BaseEntity, CallbackEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import PayloadMixin, get_device_name
from hahomematic.platforms.update import HmUpdate
from hahomematic.support import CacheEntry, Channel, check_or_create_directory, reduce_args

_LOGGER: Final = logging.getLogger(__name__)


class HmDevice(PayloadMixin):
    """Object to hold information about a device and associated entities."""

    def __init__(self, central: hmcu.CentralUnit, interface_id: str, device_address: str) -> None:
        """Initialize the device object."""
        PayloadMixin.__init__(self)
        # channel_no, base_channel_no
        self._sub_device_channels: Final[dict[int, int]] = {}
        self.central: Final = central
        self._interface_id: Final = interface_id
        self._interface: Final = central.device_details.get_interface(device_address)
        self.client: Final = central.get_client(interface_id=interface_id)
        self._device_address: Final = device_address
        self._channels: Final = central.device_descriptions.get_channels(
            interface_id, device_address
        )
        self._channel_addresses: Final[tuple[str, ...]] = tuple(self._channels.keys())
        _LOGGER.debug(
            "__INIT__: Initializing device: %s, %s",
            interface_id,
            device_address,
        )
        # {channel_no, entity}
        self._custom_entities: Final[dict[int, hmce.CustomEntity]] = {}
        self._generic_entities: Final[dict[tuple[str, str], GenericEntity]] = {}
        self._generic_events: Final[dict[tuple[str, str], GenericEvent]] = {}
        self._last_updated: datetime = INIT_DATETIME
        self._forced_availability: ForcedDeviceAvailability = ForcedDeviceAvailability.NOT_SET
        self._update_callbacks: Final[list[Callable]] = []
        self._firmware_update_callbacks: Final[list[Callable]] = []
        self._device_type: Final = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=Description.TYPE,
            )
        )
        self._sub_type: Final = str(
            central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=Description.SUBTYPE,
            )
        )
        self._ignore_for_custom_entity: Final[bool] = (
            central.parameter_visibility.device_type_is_ignored(device_type=self._device_type)
        )
        self._manufacturer = self._identify_manufacturer()
        self._product_group: Final = self.client.get_product_group(self._device_type)
        # marker if device will be created as custom entity
        self._has_custom_entity_definition: Final = (
            hmed.entity_definition_exists(device_type=self._device_type)
            and not self._ignore_for_custom_entity
        )
        self._name: Final = get_device_name(
            central=central,
            device_address=device_address,
            device_type=self._device_type,
        )
        self.value_cache: Final = ValueCache(device=self)
        self._rooms: Final = central.device_details.get_device_rooms(device_address=device_address)
        self._update_firmware_data()
        self._update_entity: Final = (
            HmUpdate(device=self) if self.device_type not in VIRTUAL_REMOTE_TYPES else None
        )
        _LOGGER.debug(
            "__INIT__: Initialized device: %s, %s, %s, %s",
            self._interface_id,
            self._device_address,
            self._device_type,
            self._name,
        )

    def _update_firmware_data(self) -> None:
        """Update firmware related data from device descriptions."""
        self._available_firmware: str | None = (
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=Description.AVAILABLE_FIRMWARE,
            )
            or None
        )
        self._firmware = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=Description.FIRMWARE,
            )
        )

        try:
            self._firmware_update_state = DeviceFirmwareState(
                str(
                    self.central.device_descriptions.get_device_parameter(
                        interface_id=self._interface_id,
                        device_address=self._device_address,
                        parameter=Description.FIRMWARE_UPDATE_STATE,
                    )
                )
            )
        except ValueError:
            self._firmware_update_state = DeviceFirmwareState.UP_TO_DATE

        self._firmware_updatable = bool(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=Description.FIRMWARE_UPDATABLE,
            )
        )

    def _identify_manufacturer(self) -> Manufacturer:
        """Identify the manufacturer of a device."""
        if self.device_type.lower().startswith("hb"):
            return Manufacturer.HB
        if self.device_type.lower().startswith("alpha"):
            return Manufacturer.MOEHLENHOFF
        return Manufacturer.EQ3

    @value_property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._forced_availability != ForcedDeviceAvailability.NOT_SET:
            return self._forced_availability == ForcedDeviceAvailability.FORCE_TRUE
        if (un_reach := self._e_unreach) is None:
            un_reach = self._e_sticky_un_reach
        if un_reach is not None and un_reach.value is not None:
            return not un_reach.value
        return True

    @config_property
    def available_firmware(self) -> str | None:
        """Return the available firmware of the device."""
        return self._available_firmware

    @property
    def channels(self) -> Mapping[str, Channel]:
        """Return the channels."""
        return self._channels

    @property
    def channel_addresses(self) -> tuple[str, ...]:
        """Return the channels."""
        return self._channel_addresses

    @property
    def config_pending(self) -> bool:
        """Return if a config change of the device is pending."""
        if self._e_config_pending is not None and self._e_config_pending.value is not None:
            return self._e_config_pending.value is True
        return False

    @property
    def custom_entities(self) -> tuple[hmce.CustomEntity, ...]:
        """Return the custom entities."""
        return tuple(self._custom_entities.values())

    @config_property
    def device_address(self) -> str:
        """Return the device_address of the device."""
        return self._device_address

    @config_property
    def device_type(self) -> str:
        """Return the device_type of the device."""
        return self._device_type

    @config_property
    def firmware(self) -> str:
        """Return the firmware of the device."""
        return self._firmware

    @config_property
    def firmware_updatable(self) -> bool:
        """Return the firmware update state of the device."""
        return self._firmware_updatable

    @config_property
    def firmware_update_state(self) -> DeviceFirmwareState:
        """Return the firmware update state of the device."""
        return self._firmware_update_state

    @property
    def generic_events(self) -> tuple[GenericEvent, ...]:
        """Return the generic events."""
        return tuple(self._generic_events.values())

    @property
    def generic_entities(self) -> tuple[GenericEntity, ...]:
        """Return the generic entities."""
        return tuple(self._generic_entities.values())

    @config_property
    def has_sub_devices(self) -> bool:
        """Return if device has multiple sub device channels."""
        return len(set(self._sub_device_channels.values())) > 1

    @config_property
    def identifier(self) -> str:
        """Return the identifier of the device."""
        return f"{self._device_address}{IDENTIFIER_SEPARATOR}{self._interface_id}"

    @config_property
    def interface(self) -> str:
        """Return the interface of the device."""
        return self._interface

    @config_property
    def interface_id(self) -> str:
        """Return the interface_id of the device."""
        return self._interface_id

    @config_property
    def ignore_for_custom_entity(self) -> bool:
        """Return if device should be ignored for custom entity."""
        return self._ignore_for_custom_entity

    @property
    def has_custom_entity_definition(self) -> bool:
        """Return if custom_entity definition is available for the device."""
        return self._has_custom_entity_definition

    @config_property
    def manufacturer(self) -> str:
        """Return the manufacturer of the device."""
        return self._manufacturer

    @config_property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @config_property
    def product_group(self) -> ProductGroup:
        """Return the product group of the device."""
        return self._product_group

    @config_property
    def room(self) -> str | None:
        """Return the room of the device, if only one assigned in CCU."""
        if self._rooms and len(self._rooms) == 1:
            return list(self._rooms)[0]
        return None

    @config_property
    def rooms(self) -> set[str]:
        """Return all rooms of the device."""
        return self._rooms

    @config_property
    def sub_type(self) -> str:
        """Return the sub_type of the device."""
        return self._sub_type

    @property
    def update_entity(self) -> HmUpdate | None:
        """Return the device firmware update entity of the device."""
        return self._update_entity

    @property
    def _e_unreach(self) -> GenericEntity | None:
        """Return th UNREACH entity."""
        return self.get_generic_entity(
            channel_address=f"{self._device_address}:0", parameter=Parameter.UN_REACH
        )

    @property
    def _e_sticky_un_reach(self) -> GenericEntity | None:
        """Return th STICKY_UN_REACH entity."""
        return self.get_generic_entity(
            channel_address=f"{self._device_address}:0", parameter=Parameter.STICKY_UN_REACH
        )

    @property
    def _e_config_pending(self) -> GenericEntity | None:
        """Return th CONFIG_PENDING entity."""
        return self.get_generic_entity(
            channel_address=f"{self._device_address}:0", parameter=Parameter.CONFIG_PENDING
        )

    def add_sub_device_channel(self, channel_no: int, base_channel_no: int) -> None:
        """Assign channel no to base channel no."""
        if base_channel_no not in self._sub_device_channels:
            self._sub_device_channels[base_channel_no] = base_channel_no
        if channel_no not in self._sub_device_channels:
            self._sub_device_channels[channel_no] = base_channel_no
        elif self._sub_device_channels[channel_no] != base_channel_no:
            return None

    def get_sub_device_channel(self, channel_no: int) -> int | None:
        """Return the sub device channel."""
        return self._sub_device_channels.get(channel_no)

    def add_entity(self, entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(entity, BaseEntity):
            self.central.add_event_subscription(entity=entity)
        if isinstance(entity, GenericEntity):
            self._generic_entities[(entity.channel_address, entity.parameter)] = entity
            self.register_update_callback(update_callback=entity.fire_update_entity_callback)
        if isinstance(entity, hmce.CustomEntity):
            self._custom_entities[entity.channel_no] = entity
        if isinstance(entity, GenericEvent):
            self._generic_events[(entity.channel_address, entity.parameter)] = entity

    def remove_entity(self, entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(entity, BaseEntity):
            self.central.remove_event_subscription(entity=entity)
        if isinstance(entity, GenericEntity):
            del self._generic_entities[(entity.channel_address, entity.parameter)]
            self.unregister_update_callback(update_callback=entity.fire_update_entity_callback)
        if isinstance(entity, hmce.CustomEntity):
            del self._custom_entities[entity.channel_no]
        if isinstance(entity, GenericEvent):
            del self._generic_events[(entity.channel_address, entity.parameter)]
        entity.fire_remove_entity_callback()

    def clear_collections(self) -> None:
        """Remove entities from collections and central."""
        for event in self.generic_events:
            self.remove_entity(event)
        self._generic_events.clear()

        for entity in self.generic_entities:
            self.remove_entity(entity)
        self._generic_entities.clear()

        for custom_entity in self.custom_entities:
            self.remove_entity(custom_entity)
        self._custom_entities.clear()

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

    def _set_last_updated(self) -> None:
        self._last_updated = datetime.now()

    def get_entities(
        self,
        platform: HmPlatform | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackEntity, ...]:
        """Get all entities of the device."""
        all_entities: tuple[CallbackEntity, ...] = (
            *self.custom_entities,
            *self.generic_entities,
            self._update_entity,  # type: ignore[arg-type]
        )

        return tuple(
            entity
            for entity in all_entities
            if entity is not None
            and (platform is None or entity.platform == platform)
            and (
                (exclude_no_create and entity.usage != EntityUsage.NO_CREATE)
                or exclude_no_create is False
            )
            and (registered is None or entity.is_registered == registered)
        )

    def get_entities_by_platform(
        self, exclude_no_create: bool = True, registered: bool | None = None
    ) -> Mapping[HmPlatform, Set[CallbackEntity]]:
        """Return all externally registered entities."""
        entities_by_platform: dict[HmPlatform, set[CallbackEntity]] = {}
        for platform in PLATFORMS:
            if platform == HmPlatform.EVENT:
                continue
            entities_by_platform[platform] = set()

        for entity in self.get_entities(
            exclude_no_create=exclude_no_create, registered=registered
        ):
            if entity.platform in PLATFORMS:
                entities_by_platform[entity.platform].add(entity)

        return entities_by_platform

    def get_channel_events(
        self, event_type: EventType, registered: bool | None = None
    ) -> Mapping[int, list[GenericEvent]]:
        """Return a list of specific events of a channel."""
        event_dict: dict[int, list[GenericEvent]] = {}
        if event_type not in ENTITY_EVENTS:
            return event_dict
        for event in self.generic_events:
            if (
                event.event_type == event_type
                and (registered is None or event.is_registered == registered)
                and event.channel_no is not None
            ):
                if event.channel_no not in event_dict:
                    event_dict[event.channel_no] = []
                event_dict[event.channel_no].append(event)

        return event_dict

    def get_custom_entity(self, channel_no: int) -> hmce.CustomEntity | None:
        """Return an entity from device."""
        return self._custom_entities.get(channel_no)

    def get_generic_entity(self, channel_address: str, parameter: str) -> GenericEntity | None:
        """Return an entity from device."""
        return self._generic_entities.get((channel_address, parameter))

    def get_generic_event(self, channel_address: str, parameter: str) -> GenericEvent | None:
        """Return a generic event from device."""
        return self._generic_events.get((channel_address, parameter))

    def get_readable_entities(self, paramset_key: ParamsetKey) -> tuple[GenericEntity, ...]:
        """Return the list of readable master entities."""
        return tuple(
            ge
            for ge in self._generic_entities.values()
            if ge.is_readable and ge.paramset_key == paramset_key
        )

    def set_forced_availability(self, forced_availability: ForcedDeviceAvailability) -> None:
        """Set the availability of the device."""
        if self._forced_availability != forced_availability:
            self._forced_availability = forced_availability
            for entity in self.generic_entities:
                entity.fire_update_entity_callback()

    async def export_device_definition(self) -> None:
        """Export the device definition for current device."""
        device_exporter = _DefinitionExporter(device=self)
        await device_exporter.export_data()

    def refresh_firmware_data(self) -> None:
        """Refresh firmware data of the device."""
        old_available_firmware = self._available_firmware
        old_firmware = self._firmware
        old_firmware_update_state = self._firmware_update_state
        old_firmware_updatable = self._firmware_updatable

        self._update_firmware_data()

        if (
            old_available_firmware != self._available_firmware
            or old_firmware != self._firmware
            or old_firmware_update_state != self._firmware_update_state
            or old_firmware_updatable != self._firmware_updatable
        ):
            for _firmware_callback in self._firmware_update_callbacks:
                _firmware_callback()

    async def update_firmware(self, refresh_after_update_intervals: tuple[int, ...]) -> bool:
        """Update the firmware of the homematic device."""
        update_result = await self.client.update_device_firmware(
            device_address=self._device_address
        )

        async def refresh_data() -> None:
            for refresh_interval in refresh_after_update_intervals:
                await asyncio.sleep(refresh_interval)
                await self.central.refresh_firmware_data(device_address=self._device_address)

        if refresh_after_update_intervals:
            self.central.create_task(target=refresh_data(), name="refresh_firmware_data")

        return update_result

    async def load_value_cache(self) -> None:
        """Init the parameter cache."""
        if len(self._generic_entities) > 0:
            await self.value_cache.init_base_entities()
        if len(self._generic_events) > 0:
            await self.value_cache.init_readable_events()
        _LOGGER.debug(
            "INIT_DATA: Skipping load_data, missing entities for %s",
            self._device_address,
        )

    async def reload_paramset_descriptions(self) -> None:
        """Reload paramset for device."""
        for (
            paramset_key,
            channel_addresses,
        ) in self.central.paramset_descriptions.get_channel_addresses_by_paramset_key(
            interface_id=self._interface_id,
            device_address=self._device_address,
        ).items():
            for channel_address in channel_addresses:
                await self.client.fetch_paramset_description(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    save_to_file=False,
                )
        await self.central.paramset_descriptions.save()
        for entity in self.generic_entities:
            entity.update_parameter_data()
        self.fire_update_device_callback()

    def fire_update_device_callback(self, *args: Any) -> None:
        """Do what is needed when the state of the device has been updated."""
        self._set_last_updated()
        for _callback in self._update_callbacks:
            try:
                _callback(*args)
            except Exception as ex:
                _LOGGER.warning("FIRE_UPDATE_DEVICE failed: %s", reduce_args(args=ex.args))

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address: {self._device_address}, "
            f"type: {len(self._device_type)}, "
            f"name: {self._name}, "
            f"generic_entities: {len(self._generic_entities)}, "
            f"custom_entities: {len(self._custom_entities)}, "
            f"events: {len(self._generic_events)}"
        )


class ValueCache:
    """A Cache to temporarily stored values."""

    _NO_VALUE_CACHE_ENTRY: Final = "NO_VALUE_CACHE_ENTRY"

    def __init__(self, device: HmDevice) -> None:
        """Init the value cache."""
        self._sema_get_or_load_value: Final = asyncio.Semaphore()
        self._device: Final = device
        # {key, CacheEntry}
        self._device_cache: Final[dict[str, CacheEntry]] = {}

    async def init_base_entities(self) -> None:
        """Load data by get_value."""
        try:
            for entity in self._get_base_entities():
                value = await self.get_value(
                    channel_address=entity.channel_address,
                    paramset_key=entity.paramset_key,
                    parameter=entity.parameter,
                    call_source=CallSource.HM_INIT,
                )
                entity.write_value(value=value)
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "init_base_entities: Failed to init cache for channel0 %s, %s [%s]",
                self._device.device_type,
                self._device.device_address,
                ex,
            )

    def _get_base_entities(self) -> set[GenericEntity]:
        """Get entities of channel 0 and master."""
        entities: list[GenericEntity] = []
        for entity in self._device.generic_entities:
            if (
                entity.channel_no == 0
                and entity.paramset_key == ParamsetKey.VALUES
                and entity.parameter in RELEVANT_INIT_PARAMETERS
            ) or entity.paramset_key == ParamsetKey.MASTER:
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
                    call_source=CallSource.HM_INIT,
                )
                event.write_value(value=value)
        except BaseHomematicException as ex:
            _LOGGER.debug(
                "init_base_events: Failed to init cache for channel0 %s, %s [%s]",
                self._device.device_type,
                self._device.device_address,
                ex,
            )

    def _get_readable_events(self) -> set[GenericEvent]:
        """Get readable events."""
        events: list[GenericEvent] = []
        for event in self._device.generic_events:
            if event.is_readable:
                events.append(event)
        return set(events)

    async def get_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        call_source: CallSource,
        direct_call: bool = False,
    ) -> Any:
        """Load data."""
        async with self._sema_get_or_load_value:
            if (
                direct_call is False
                and (
                    cached_value := self._get_value_from_cache(
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                    )
                )
                != NO_CACHE_ENTRY
            ):
                return (
                    NO_CACHE_ENTRY if cached_value == self._NO_VALUE_CACHE_ENTRY else cached_value
                )

            value: Any = self._NO_VALUE_CACHE_ENTRY
            try:
                value = await self._device.client.get_value(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    call_source=call_source,
                )
            except BaseHomematicException as ex:
                _LOGGER.debug(
                    "GET_OR_LOAD_VALUE: Failed to get data for %s, %s, %s: %s",
                    self._device.device_type,
                    channel_address,
                    parameter,
                    ex,
                )
            self._add_entry_to_device_cache(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=parameter,
                value=value,
            )

            return NO_CACHE_ENTRY if value == self._NO_VALUE_CACHE_ENTRY else value

    @staticmethod
    def _get_key(channel_address: str, paramset_key: str, parameter: str) -> str:
        """Get the key for the cache entry."""
        return f"{channel_address}.{paramset_key}.{parameter}"

    def _add_entry_to_device_cache(
        self, channel_address: str, paramset_key: str, parameter: str, value: Any
    ) -> None:
        """Add value to cache."""
        key = self._get_key(
            channel_address=channel_address, paramset_key=paramset_key, parameter=parameter
        )
        # write value to cache even if an exception has occurred
        # to avoid repetitive calls to CCU within max_age
        self._device_cache[key] = CacheEntry(value=value, last_refresh=datetime.now())

    def _get_value_from_cache(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
    ) -> Any:
        """Load data from caches."""
        # Try to get data from central cache
        if (
            paramset_key == ParamsetKey.VALUES
            and (
                global_value := self._device.central.data_cache.get_data(
                    interface=self._device.interface,
                    channel_address=channel_address,
                    parameter=parameter,
                )
            )
            != NO_CACHE_ENTRY
        ):
            return global_value

        # Try to get data from device cache
        key = self._get_key(
            channel_address=channel_address, paramset_key=paramset_key, parameter=parameter
        )
        if (
            cache_entry := self._device_cache.get(key, CacheEntry.empty())
        ) and cache_entry.is_valid:
            return cache_entry.value
        return NO_CACHE_ENTRY


class _DefinitionExporter:
    """Export device definitions from cache."""

    def __init__(self, device: HmDevice) -> None:
        """Init the device exporter."""
        self._client: Final = device.client
        self._central: Final = device.client.central
        self._storage_folder: Final = self._central.config.storage_folder
        self._interface_id: Final = device.interface_id
        self._device_address: Final = device.device_address
        self._random_id: Final[str] = f"VCU{int(random.randint(1000000, 9999999))}"

    async def export_data(self) -> None:
        """Export data."""
        device_descriptions: Mapping[str, Any] = (
            self._central.device_descriptions.get_device_with_channels(
                interface_id=self._interface_id, device_address=self._device_address
            )
        )
        paramset_descriptions: Mapping[
            str, Any
        ] = await self._client.get_all_paramset_descriptions(tuple(device_descriptions.values()))
        device_type = device_descriptions[self._device_address][Description.TYPE]
        filename = f"{device_type}.json"

        # anonymize device_descriptions
        anonymize_device_descriptions: list[Any] = []
        for device_description in device_descriptions.values():
            if device_description == {}:
                continue  # pragma: no cover
            new_device_description = copy(device_description)
            new_device_description[Description.ADDRESS] = self._anonymize_address(
                address=new_device_description[Description.ADDRESS]
            )
            if new_device_description.get(Description.PARENT):
                new_device_description[Description.PARENT] = new_device_description[
                    Description.ADDRESS
                ].split(":")[0]
            elif new_device_description.get(Description.CHILDREN):
                new_device_description[Description.CHILDREN] = [
                    self._anonymize_address(a)
                    for a in new_device_description[Description.CHILDREN]
                ]
            anonymize_device_descriptions.append(new_device_description)

        # anonymize paramset_descriptions
        anonymize_paramset_descriptions: dict[str, Any] = {}
        for address, paramset_description in paramset_descriptions.items():
            anonymize_paramset_descriptions[self._anonymize_address(address=address)] = (
                paramset_description
            )

        # Save device_descriptions for device to file.
        await self._save(
            file_dir=f"{self._storage_folder}/{DEFAULT_DEVICE_DESCRIPTIONS_DIR}",
            filename=filename,
            data=anonymize_device_descriptions,
        )

        # Save device_descriptions for device to file.
        await self._save(
            file_dir=f"{self._storage_folder}/{DEFAULT_PARAMSET_DESCRIPTIONS_DIR}",
            filename=filename,
            data=anonymize_paramset_descriptions,
        )

    def _anonymize_address(self, address: str) -> str:
        address_parts = address.split(":")
        address_parts[0] = self._random_id
        return ":".join(address_parts)

    async def _save(self, file_dir: str, filename: str, data: Any) -> DataOperationResult:
        """Save file to disk."""

        def _save() -> DataOperationResult:
            if not check_or_create_directory(file_dir):
                return DataOperationResult.NO_SAVE  # pragma: no cover
            with open(
                file=os.path.join(file_dir, filename),
                mode="wb",
            ) as fptr:
                fptr.write(
                    orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
                )
            return DataOperationResult.SAVE_SUCCESS

        return await self._central.async_add_executor_job(_save)
