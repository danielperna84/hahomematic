"""Module for the Device class."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from copy import copy
from dataclasses import dataclass
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
    HM_VIRTUAL_REMOTE_TYPES,
    IDENTIFIER_SEPARATOR,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    RELEVANT_INIT_PARAMETERS,
    HmCallSource,
    HmDataOperationResult,
    HmDescription,
    HmDeviceFirmwareState,
    HmEvent,
    HmEventType,
    HmForcedDeviceAvailability,
    HmInterfaceName,
    HmManufacturer,
    HmParamsetKey,
    HmProductGroup,
)
from hahomematic.exceptions import BaseHomematicException
from hahomematic.platforms.custom import definition as hmed, entity as hmce
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.entity import BaseEntity, CallbackEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity, WrapperEntity
from hahomematic.platforms.support import PayloadMixin, get_device_name
from hahomematic.platforms.update import HmUpdate
from hahomematic.support import check_or_create_directory, updated_within_seconds

_LOGGER: Final = logging.getLogger(__name__)


class HmDevice(PayloadMixin):
    """Object to hold information about a device and associated entities."""

    def __init__(self, central: hmcu.CentralUnit, interface_id: str, device_address: str) -> None:
        """Initialize the device object."""
        PayloadMixin.__init__(self)
        self.central: Final = central
        self._interface_id: Final = interface_id
        self._interface: Final = central.device_details.get_interface(device_address)
        self.client: Final = central.get_client(interface_id=interface_id)
        self._device_address: Final = device_address
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
        self._last_update: datetime = INIT_DATETIME
        self._forced_availability: HmForcedDeviceAvailability = HmForcedDeviceAvailability.NOT_SET
        self._update_callbacks: Final[list[Callable]] = []
        self._firmware_update_callbacks: Final[list[Callable]] = []
        self._device_type: Final = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HmDescription.TYPE,
            )
        )
        self._sub_type: Final = str(
            central.device_descriptions.get_device_parameter(
                interface_id=interface_id,
                device_address=device_address,
                parameter=HmDescription.SUBTYPE,
            )
        )
        self._manufacturer = self._identify_manufacturer()
        self._product_group: Final = self._identify_product_group()
        # marker if device will be created as custom entity
        self._has_custom_entity_definition: Final = hmed.entity_definition_exists(
            device_type=self._device_type
        )
        self._name: Final = get_device_name(
            central=central,
            device_address=device_address,
            device_type=self._device_type,
        )
        self.value_cache: Final = ValueCache(device=self)
        self._room: Final = central.device_details.get_room(device_address=device_address)
        self._update_firmware_data()
        self._update_entity: Final = (
            HmUpdate(device=self) if self.device_type not in HM_VIRTUAL_REMOTE_TYPES else None
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
                parameter=HmDescription.AVAILABLE_FIRMWARE,
            )
            or None
        )
        self._firmware = str(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=HmDescription.FIRMWARE,
            )
        )

        try:
            self._firmware_update_state = HmDeviceFirmwareState(
                str(
                    self.central.device_descriptions.get_device_parameter(
                        interface_id=self._interface_id,
                        device_address=self._device_address,
                        parameter=HmDescription.FIRMWARE_UPDATE_STATE,
                    )
                )
            )
        except ValueError:
            self._firmware_update_state = HmDeviceFirmwareState.UP_TO_DATE

        self._firmware_updatable = bool(
            self.central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=HmDescription.FIRMWARE_UPDATABLE,
            )
        )

    def _identify_manufacturer(self) -> HmManufacturer:
        """Identify the manufacturer of a device."""
        if self.device_type.lower().startswith("hb"):
            return HmManufacturer.HB
        if self.device_type.lower().startswith("alpha"):
            return HmManufacturer.MOEHLENHOFF
        return HmManufacturer.EQ3

    def _identify_product_group(self) -> HmProductGroup:
        """Identify the product group of the homematic device."""
        if self.interface == HmInterfaceName.HMIP_RF:
            l_device_type = self.device_type.lower()
            if l_device_type.startswith("hmipw"):
                return HmProductGroup.HMIPW
            if l_device_type.startswith("hmip"):
                return HmProductGroup.HMIP
        if self.interface == HmInterfaceName.BIDCOS_WIRED:
            return HmProductGroup.HMW
        if self.interface == HmInterfaceName.BIDCOS_RF:
            return HmProductGroup.HM
        if self.interface == HmInterfaceName.VIRTUAL_DEVICES:
            return HmProductGroup.VIRTUAL
        return HmProductGroup.UNKNOWN

    @value_property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._forced_availability != HmForcedDeviceAvailability.NOT_SET:
            return self._forced_availability == HmForcedDeviceAvailability.FORCE_TRUE
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
    def config_pending(self) -> bool:
        """Return if a config change of the device is pending."""
        if self._e_config_pending is not None and self._e_config_pending.value is not None:
            return self._e_config_pending.value is True
        return False

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
    def firmware_update_state(self) -> HmDeviceFirmwareState:
        """Return the firmware update state of the device."""
        return self._firmware_update_state

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
    def product_group(self) -> HmProductGroup:
        """Return the product group of the device."""
        return self._product_group

    @config_property
    def room(self) -> str | None:
        """Return the room of the device."""
        return self._room

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
        return self.generic_entities.get((f"{self._device_address}:0", HmEvent.UN_REACH))

    @property
    def _e_sticky_un_reach(self) -> GenericEntity | None:
        """Return th STICKY_UN_REACH entity."""
        return self.generic_entities.get((f"{self._device_address}:0", HmEvent.STICKY_UN_REACH))

    @property
    def _e_config_pending(self) -> GenericEntity | None:
        """Return th CONFIG_PENDING entity."""
        return self.generic_entities.get((f"{self._device_address}:0", HmEvent.CONFIG_PENDING))

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
        self._last_update = datetime.now()

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

    async def load_value_cache(self, max_age: int = MAX_CACHE_AGE) -> None:
        """Init the parameter cache."""
        if len(self.generic_entities) > 0:
            await self.value_cache.init_base_entities(max_age=max_age)
        if len(self.generic_events) > 0:
            await self.value_cache.init_readable_events(max_age=max_age)
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
            f"address: {self._device_address}, "
            f"type: {len(self._device_type)}, "
            f"name: {self._name}, "
            f"generic_entities: {len(self.generic_entities)}, "
            f"custom_entities: {len(self.custom_entities)}, "
            f"wrapper_entities: {len(self.wrapper_entities)}, "
            f"events: {len(self.generic_events)}"
        )


class ValueCache:
    """A Cache to temporarily stored values."""

    _NO_VALUE_CACHE_ENTRY: Final = "NO_VALUE_CACHE_ENTRY"

    def __init__(self, device: HmDevice) -> None:
        """Init the value cache."""
        self._sema_get_or_load_value: Final = asyncio.Semaphore()
        self._device: Final = device
        # { parparamset_key, {channel_address, {parameter, CacheEntry}}}
        self._device_cache: Final[dict[str, dict[str, dict[str, CacheEntry]]]] = {}

    async def init_base_entities(self, max_age: int) -> None:
        """Load data by get_value."""
        try:
            for entity in self._get_base_entities():
                value = await self.get_value(
                    channel_address=entity.channel_address,
                    paramset_key=entity.paramset_key,
                    parameter=entity.parameter,
                    call_source=HmCallSource.HM_INIT,
                    max_age=max_age,
                )
                entity.update_value(value=value)
        except BaseHomematicException as bhe:
            _LOGGER.debug(
                "init_base_entities: Failed to init cache for channel0 %s, %s [%s]",
                self._device.device_type,
                self._device.device_address,
                bhe,
            )

    def _get_base_entities(self) -> set[GenericEntity]:
        """Get entities of channel 0 and master."""
        entities: list[GenericEntity] = []
        for entity in self._device.generic_entities.values():
            if (
                entity.channel_no == 0
                and entity.paramset_key == HmParamsetKey.VALUES
                and entity.parameter in RELEVANT_INIT_PARAMETERS
            ) or entity.paramset_key == HmParamsetKey.MASTER:
                entities.append(entity)
        return set(entities)

    async def init_readable_events(self, max_age: int) -> None:
        """Load data by get_value."""
        try:
            for event in self._get_readable_events():
                value = await self.get_value(
                    channel_address=event.channel_address,
                    paramset_key=event.paramset_key,
                    parameter=event.parameter,
                    call_source=HmCallSource.HM_INIT,
                    max_age=max_age,
                )
                event.update_value(value=value)
        except BaseHomematicException as bhe:
            _LOGGER.debug(
                "init_base_events: Failed to init cache for channel0 %s, %s [%s]",
                self._device.device_type,
                self._device.device_address,
                bhe,
            )

    def _get_readable_events(self) -> set[GenericEvent]:
        """Get readable events."""
        events: list[GenericEvent] = []
        for event in self._device.generic_events.values():
            if event.is_readable:
                events.append(event)
        return set(events)

    async def get_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        call_source: HmCallSource,
        max_age: int,
    ) -> Any:
        """Load data."""
        async with self._sema_get_or_load_value:
            if (
                cached_value := self._get_value_from_cache(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    max_age=max_age,
                )
            ) != NO_CACHE_ENTRY:
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
            except BaseHomematicException as bhe:
                _LOGGER.debug(
                    "GET_OR_LOAD_VALUE: Failed to get data for %s, %s, %s: %s",
                    self._device.device_type,
                    channel_address,
                    parameter,
                    bhe,
                )
            self._add_entry_to_device_cache(
                channel_address=channel_address,
                paramset_key=paramset_key,
                parameter=parameter,
                value=value,
            )

            return NO_CACHE_ENTRY if value == self._NO_VALUE_CACHE_ENTRY else value

    def _add_entry_to_device_cache(
        self, channel_address: str, paramset_key: str, parameter: str, value: Any
    ) -> None:
        """Add value to cache."""
        if paramset_key not in self._device_cache:
            self._device_cache[paramset_key] = {}
        if channel_address not in self._device_cache[paramset_key]:
            self._device_cache[paramset_key][channel_address] = {}
        # write value to cache even if an exception has occurred
        # to avoid repetitive calls to CCU within max_age
        self._device_cache[paramset_key][channel_address][parameter] = CacheEntry(
            value=value, last_update=datetime.now()
        )

    def _get_value_from_cache(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        max_age: int,
    ) -> Any:
        """Load data from caches."""
        # Try to get data from central cache
        if (
            global_value := self._device.central.device_data.get_device_data(
                interface=self._device.interface,
                channel_address=channel_address,
                parameter=parameter,
                max_age=max_age,
            )
        ) != NO_CACHE_ENTRY:
            return global_value

        # Try to get data from device cache
        if (
            cache_entry := self._device_cache.get(paramset_key, {})
            .get(channel_address, {})
            .get(
                parameter,
                CacheEntry.empty(),
            )
        ) and cache_entry.is_valid(max_age=max_age):
            return cache_entry.value
        return NO_CACHE_ENTRY


@dataclass(slots=True)
class CacheEntry:
    """An entry for the value cache."""

    value: Any
    last_update: datetime

    @staticmethod
    def empty() -> CacheEntry:
        """Return empty cache entry."""
        return CacheEntry(value=NO_CACHE_ENTRY, last_update=datetime.min)

    def is_valid(self, max_age: int) -> bool:
        """Return if entry is valid."""
        if self.value == NO_CACHE_ENTRY:
            return False
        return updated_within_seconds(last_update=self.last_update, max_age=max_age)


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
        device_descriptions: dict[
            str, Any
        ] = self._central.device_descriptions.get_device_with_channels(
            interface_id=self._interface_id, device_address=self._device_address
        )
        paramset_descriptions: dict[str, Any] = await self._client.get_all_paramset_descriptions(
            list(device_descriptions.values())
        )
        device_type = device_descriptions[self._device_address][HmDescription.TYPE]
        filename = f"{device_type}.json"

        # anonymize device_descriptions
        anonymize_device_descriptions: list[Any] = []
        for device_description in device_descriptions.values():
            if device_description == {}:
                continue  # pragma: no cover
            new_device_description = copy(device_description)
            new_device_description[HmDescription.ADDRESS] = self._anonymize_address(
                address=new_device_description[HmDescription.ADDRESS]
            )
            if new_device_description.get(HmDescription.PARENT):
                new_device_description[HmDescription.PARENT] = new_device_description[
                    HmDescription.ADDRESS
                ].split(":")[0]
            elif new_device_description.get(HmDescription.CHILDREN):
                new_device_description[HmDescription.CHILDREN] = [
                    self._anonymize_address(a)
                    for a in new_device_description[HmDescription.CHILDREN]
                ]
            anonymize_device_descriptions.append(new_device_description)

        # anonymize paramset_descriptions
        anonymize_paramset_descriptions: dict[str, Any] = {}
        for address, paramset_description in paramset_descriptions.items():
            anonymize_paramset_descriptions[
                self._anonymize_address(address=address)
            ] = paramset_description

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

    async def _save(self, file_dir: str, filename: str, data: Any) -> HmDataOperationResult:
        """Save file to disk."""

        def _save() -> HmDataOperationResult:
            if not check_or_create_directory(file_dir):
                return HmDataOperationResult.NO_SAVE  # pragma: no cover
            with open(
                file=os.path.join(file_dir, filename),
                mode="wb",
            ) as fptr:
                fptr.write(
                    orjson.dumps(data, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS)
                )
            return HmDataOperationResult.SAVE_SUCCESS

        return await self._central.async_add_executor_job(_save)
