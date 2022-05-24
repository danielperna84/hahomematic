"""
Module for the Device class.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

import hahomematic.central_unit as hm_central
import hahomematic.client as hm_client
from hahomematic.const import (
    ATTR_HM_FIRMWARE,
    ATTR_HM_FLAGS,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SUBTYPE,
    ATTR_HM_TYPE,
    BUTTON_ACTIONS,
    CLICK_EVENTS,
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    FLAG_INTERAL,
    HM_VIRTUAL_REMOTES,
    IDENTIFIERS_SEPARATOR,
    INIT_DATETIME,
    MANUFACTURER,
    OPERATION_EVENT,
    OPERATION_READ,
    OPERATION_WRITE,
    PARAMSET_KEY_VALUES,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
)
from hahomematic.devices import entity_definition_exists, get_device_funcs
from hahomematic.entity import (
    BaseEntity,
    BaseEvent,
    CallbackEntity,
    ClickEvent,
    CustomEntity,
    GenericEntity,
)
from hahomematic.exceptions import BaseHomematicException
from hahomematic.helpers import (
    HmDeviceInfo,
    generate_unique_id,
    get_channel_no,
    get_device_channel,
    get_device_name,
    updated_within_seconds,
)
from hahomematic.internal.action import HmAction
from hahomematic.internal.text import HmText
from hahomematic.platforms.binary_sensor import HmBinarySensor
from hahomematic.platforms.button import HmButton
from hahomematic.platforms.number import HmFloat, HmInteger
from hahomematic.platforms.select import HmSelect
from hahomematic.platforms.sensor import HmSensor
from hahomematic.platforms.switch import HmSwitch
import hahomematic.support as hm_support

NO_CACHE_ENTRY = "NO_CACHE_ENTRY"
_LOGGER = logging.getLogger(__name__)


class HmDevice:
    """
    Object to hold information about a device and associated entities.
    """

    def __init__(
        self, central: hm_central.CentralUnit, interface_id: str, device_address: str
    ):
        """
        Initialize the device object.
        """
        self._central = central
        self._interface_id = interface_id
        self._interface = self._central.device_details.get_interface(device_address)
        self._client = self._central.clients[self._interface_id]
        self._device_address = device_address
        self._channels = self._central.device_descriptions.get_channels(
            self._interface_id, self._device_address
        )
        _LOGGER.debug(
            "__init__: Initializing device: %s, %s",
            self._interface_id,
            self._device_address,
        )
        self.entities: dict[tuple[str, str], GenericEntity] = {}
        self.custom_entities: dict[str, CustomEntity] = {}
        self.action_events: dict[tuple[str, str], BaseEvent] = {}
        self.last_update: datetime = INIT_DATETIME
        self._available: bool = True
        self._update_callbacks: list[Callable] = []
        self.device_type: str = str(
            self._central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=ATTR_HM_TYPE,
            )
        )
        self.sub_type: str = str(
            self._central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=ATTR_HM_SUBTYPE,
            )
        )
        # marker if device will be created as custom entity
        self.is_custom_entity: bool = entity_definition_exists(
            self.device_type, self.sub_type
        )
        self.firmware: str = str(
            self._central.device_descriptions.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=ATTR_HM_FIRMWARE,
            )
        )

        self.name = get_device_name(
            central=self._central,
            device_address=device_address,
            device_type=self.device_type,
        )
        self._value_cache = ValueCache(device=self)

        _LOGGER.debug(
            "__init__: Initialized device: %s, %s, %s, %s",
            self._interface_id,
            self._device_address,
            self.device_type,
            self.name,
        )

    @property
    def central(self) -> hm_central.CentralUnit:
        """Return the central unit."""
        return self._central

    @property
    def client(self) -> hm_client.Client:
        """Return the client."""
        return self._client

    @property
    def interface(self) -> str:
        """Return the interface of the client."""
        return self._interface

    @property
    def interface_id(self) -> str:
        """Return the interface_id."""
        return self._interface_id

    @property
    def device_address(self) -> str:
        """Return the address."""
        return self._device_address

    @property
    def channels(self) -> list[str]:
        """Return the channels."""
        return self._channels

    @property
    def room(self) -> str | None:
        """Return the room."""
        return self._central.device_details.get_room(
            device_address=self._device_address
        )

    @property
    def value_cache(self) -> ValueCache:
        """Return the value cache."""
        return self._value_cache

    @property
    def _e_unreach(self) -> GenericEntity | None:
        """Return th UNREACH entity"""
        return self.entities.get((f"{self._device_address}:0", EVENT_UN_REACH))

    @property
    def _e_sticky_un_reach(self) -> GenericEntity | None:
        """Return th STICKY_UN_REACH entity"""
        return self.entities.get((f"{self._device_address}:0", EVENT_STICKY_UN_REACH))

    @property
    def _e_config_pending(self) -> GenericEntity | None:
        """Return th CONFIG_PENDING entity"""
        return self.entities.get((f"{self._device_address}:0", EVENT_CONFIG_PENDING))

    def add_hm_entity(self, hm_entity: BaseEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(hm_entity, GenericEntity):
            self.entities[(hm_entity.channel_address, hm_entity.parameter)] = hm_entity
            self.register_update_callback(hm_entity.update_entity)
        if isinstance(hm_entity, CustomEntity):
            self.custom_entities[hm_entity.unique_id] = hm_entity

    def remove_hm_entity(self, hm_entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(hm_entity, GenericEntity):
            del self.entities[(hm_entity.channel_address, hm_entity.parameter)]
            self.unregister_update_callback(hm_entity.update_entity)
        if isinstance(hm_entity, CustomEntity):
            del self.custom_entities[hm_entity.unique_id]

    def add_hm_action_event(self, hm_event: BaseEvent) -> None:
        """Add a hm entity to a device."""
        self.action_events[(hm_event.channel_address, hm_event.parameter)] = hm_event

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions."""
        for entity in self.entities.values():
            if isinstance(entity, GenericEntity):
                entity.remove_event_subscriptions()
        for action_event in self.action_events.values():
            action_event.remove_event_subscriptions()

    def remove_from_collections(self) -> None:
        """Remove entities from collections and central."""

        entities = list(self.entities.values())
        for entity in entities:
            if entity.unique_id in self._central.hm_entities:
                del self._central.hm_entities[entity.unique_id]
            self.remove_hm_entity(entity)
        self.entities.clear()

        custom_entities = list(self.custom_entities.values())
        for custom_entity in custom_entities:
            if custom_entity.unique_id in self._central.hm_entities:
                del self._central.hm_entities[custom_entity.unique_id]
            self.remove_hm_entity(custom_entity)
        self.custom_entities.clear()

        self.action_events.clear()

    def register_update_callback(self, update_callback: Callable) -> None:
        """Register update callback."""
        if callable(update_callback) and update_callback not in self._update_callbacks:
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """Remove update callback."""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_device(self, *args: Any) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(*args)

    async def export_device_definition(self) -> None:
        """Export the device definition for current device."""
        await hm_support.save_device_definition(
            client=self._client,
            interface_id=self._interface_id,
            device_address=self._device_address,
        )

    def _set_last_update(self) -> None:
        self.last_update = datetime.now()

    def get_hm_entity(
        self, channel_address: str, parameter: str
    ) -> GenericEntity | None:
        """Return a hm_entity from device."""
        return self.entities.get((channel_address, parameter))

    def __str__(self) -> str:
        """
        Provide some useful information.
        """
        return f"address: {self._device_address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}"

    @property
    def device_information(self) -> HmDeviceInfo:
        """Return device specific attributes."""
        return HmDeviceInfo(
            interface=self._interface_id,
            address=self._device_address,
            identifier=f"{self._device_address}{IDENTIFIERS_SEPARATOR}{self._interface_id}",
            manufacturer=MANUFACTURER,
            name=self.name,
            model=self.device_type,
            version=self.firmware,
            room=self.room,
            central=self._central.instance_name,
        )

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._available is False:
            return False
        un_reach = self._e_unreach
        if un_reach is None:
            un_reach = self._e_sticky_un_reach
        if un_reach is not None and un_reach.value is not None:
            return not un_reach.value
        return True

    @property
    def config_pending(self) -> bool:
        """Return if a config change of the device is pending."""
        if (
            self._e_config_pending is not None
            and self._e_config_pending.value is not None
        ):
            return self._e_config_pending.value is True
        return False

    def set_availability(self, value: bool) -> None:
        """Set the availability of the device."""
        if not self._available == value:
            self._available = value
            for entity in self.entities.values():
                entity.update_entity()

    async def reload_paramset_descriptions(self) -> None:
        """Reload paramset for device."""
        for (
            paramset_key,
            channel_addresses,
        ) in self._central.paramset_descriptions.get_device_channels_by_paramset(
            interface_id=self.interface_id, device_address=self.device_address
        ).items():
            for channel_address in channel_addresses:
                await self._client.fetch_paramset_description(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    save_to_file=False,
                )
        await self.central.paramset_descriptions.save()
        for entity in self.entities.values():
            entity.update_parameter_data()
        self.update_device()

    async def load_value_cache(self) -> None:
        """Init the parameter cache."""
        if len(self.entities) > 0:
            await self._value_cache.init_entities_channel0()
        _LOGGER.debug(
            "init_data: Skipping load_data, missing entities for %s.",
            self.device_address,
        )

    def create_entities_and_append_to_device(self) -> None:
        """
        Create the entities associated to this device.
        """
        for channel_address in self._channels:
            if (device_channel := get_channel_no(channel_address)) is None:
                _LOGGER.warning(
                    "create_entities: Wrong format of channel_address %s.",
                    channel_address,
                )
                continue

            if not self._central.paramset_descriptions.get_by_interface_channel_address(
                interface_id=self._interface_id, channel_address=channel_address
            ):
                _LOGGER.debug(
                    "create_entities: Skipping channel %s, missing paramsets.",
                    channel_address,
                )
                continue
            for (
                paramset_key
            ) in self._central.paramset_descriptions.get_by_interface_channel_address(
                interface_id=self._interface_id, channel_address=channel_address
            ):
                if not self._central.parameter_visibility.is_relevant_paramset(
                    device_type=self.device_type,
                    sub_type=self.sub_type,
                    device_channel=device_channel,
                    paramset_key=paramset_key,
                ):
                    continue
                for (
                    parameter,
                    parameter_data,
                ) in self._central.paramset_descriptions.get_by_interface_channel_address_paramset_key(
                    interface_id=self._interface_id,
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                ).items():
                    if (
                        parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT
                        and parameter in CLICK_EVENTS
                    ):
                        self._create_event_and_append_to_device(
                            channel_address=channel_address,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if self.device_type in HM_VIRTUAL_REMOTES:
                            self._create_action_and_append_to_device(
                                channel_address=channel_address,
                                paramset_key=paramset_key,
                                parameter=parameter,
                                parameter_data=parameter_data,
                            )

                    if (
                        not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT
                        and not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE
                    ) or (
                        parameter_data[ATTR_HM_FLAGS] & FLAG_INTERAL
                        and not self._central.parameter_visibility.parameter_is_un_ignored(
                            device_type=self.device_type,
                            sub_type=self.sub_type,
                            device_channel=device_channel,
                            paramset_key=paramset_key,
                            parameter=parameter,
                        )
                    ):
                        _LOGGER.debug(
                            "create_entities: Skipping %s (no event or internal)",
                            parameter,
                        )
                        continue
                    if parameter not in CLICK_EVENTS:
                        self._create_entity_and_append_to_device(
                            channel_address=channel_address,
                            paramset_key=paramset_key,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )

        # create custom entities
        if self.is_custom_entity:
            _LOGGER.debug(
                "create_entities: Handling custom entity integration: %s, %s, %s",
                self._interface_id,
                self._device_address,
                self.device_type,
            )

            # Call the custom creation function.
            for (device_func, group_base_channels) in get_device_funcs(
                self.device_type, self.sub_type
            ):
                device_func(self, self._device_address, group_base_channels)

    def _create_action_and_append_to_device(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ) -> None:
        """Create the actions associated to this device"""
        unique_id = generate_unique_id(
            central=self._central,
            address=channel_address,
            parameter=parameter,
            prefix=f"button_{self._central.instance_name}",
        )
        _LOGGER.debug(
            "create_action_and_append_to_device: Creating action for %s, %s, %s",
            channel_address,
            parameter,
            self._interface_id,
        )

        if action := HmAction(
            device=self,
            unique_id=unique_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        ):
            action.add_to_collections()

    def _create_event_and_append_to_device(
        self, channel_address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> None:
        """Create action event entity."""
        if (channel_address, parameter) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []

        unique_id = generate_unique_id(
            central=self._central,
            address=channel_address,
            parameter=parameter,
            prefix=f"event_{self._central.instance_name}",
        )

        _LOGGER.debug(
            "create_event_and_append_to_device: Creating event for %s, %s, %s",
            channel_address,
            parameter,
            self._interface_id,
        )
        action_event: BaseEvent | None = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
            if parameter in CLICK_EVENTS:
                action_event = ClickEvent(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if action_event:
            action_event.add_to_collections()

    def _create_entity_and_append_to_device(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ) -> None:
        """
        Helper that looks at the paramsets, decides which default
        platform should be used, and creates the required entities.
        """
        if self._central.parameter_visibility.ignore_parameter(
            device_type=self.device_type,
            sub_type=self.sub_type,
            device_channel=get_device_channel(channel_address),
            paramset_key=paramset_key,
            parameter=parameter,
        ):
            _LOGGER.debug(
                "create_entity_and_append_to_device: Ignoring parameter: %s [%s]",
                parameter,
                channel_address,
            )
            return None
        if (channel_address, parameter) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []

        unique_id = generate_unique_id(
            central=self._central, address=channel_address, parameter=parameter
        )
        if unique_id in self._central.hm_entities:
            _LOGGER.debug(
                "create_entity_and_append_to_device: Skipping %s (already exists)",
                unique_id,
            )
            return None
        _LOGGER.debug(
            "create_entity_and_append_to_device: Creating entity for %s, %s, %s",
            channel_address,
            parameter,
            self._interface_id,
        )
        entity: GenericEntity | None = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
            if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: action (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    if parameter in BUTTON_ACTIONS:
                        entity = HmButton(
                            device=self,
                            unique_id=unique_id,
                            channel_address=channel_address,
                            paramset_key=paramset_key,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                    else:
                        entity = HmAction(
                            device=self,
                            unique_id=unique_id,
                            channel_address=channel_address,
                            paramset_key=paramset_key,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                else:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: switch (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
            else:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: action (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmAction(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: switch: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: select: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmSelect(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_FLOAT:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: number.integer: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmFloat(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_INTEGER:
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: number.float: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmInteger(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                    # There is currently no entity platform in HA for this.
                    _LOGGER.debug(
                        "create_entity_and_append_to_device: text: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmText(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                else:
                    _LOGGER.warning(
                        "create_entity_and_append_to_device: unsupported actor: %s %s %s",
                        channel_address,
                        parameter,
                        parameter_data[ATTR_HM_TYPE],
                    )
        else:
            # Also check, if sensor could be a binary_sensor due to value_list.
            if _is_binary_sensor(parameter_data):
                _LOGGER.debug(
                    "create_entity_and_append_to_device: binary_sensor: %s %s",
                    channel_address,
                    parameter,
                )
                parameter_data[ATTR_HM_TYPE] = TYPE_BOOL
                entity = HmBinarySensor(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            else:
                _LOGGER.debug(
                    "create_entity_and_append_to_device: sensor: %s %s",
                    channel_address,
                    parameter,
                )
                entity = HmSensor(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if entity:
            entity.add_to_collections()


class ValueCache:
    """A Cache to temporaily stored values"""

    _sema_get_or_load_value = asyncio.BoundedSemaphore(1)

    def __init__(self, device: HmDevice):
        self._device = device
        self._client = device.client
        # { parparamset_key, {channel_address, {parameter, CacheEntry}}}
        self._value_cache: dict[str, dict[str, dict[str, CacheEntry]]] = {}

    async def init_entities_channel0(self) -> None:
        """Load data by get_value"""
        try:
            for entity in self._get_entities_channel0():
                value = await self.get_value(
                    channel_address=entity.channel_address,
                    paramset_key=entity.paramset_key,
                    parameter=entity.parameter,
                )
                entity.set_value(value=value)
        except BaseHomematicException as bhe:
            _LOGGER.debug(
                "init_values_channel0: Failed to init cache for channel0 %s, %s [%s]",
                self._device.device_type,
                self._device.device_address,
                bhe,
            )

    def _get_entities_channel0(self) -> set[GenericEntity]:
        """Get entities by channel address and parameter."""
        entities: list[GenericEntity] = []
        for entity in self._device.entities.values():
            if (
                entity.operations & OPERATION_READ
                and entity.channel_no == 0
                and entity.paramset_key == PARAMSET_KEY_VALUES
            ):
                entities.append(entity)
        return set(entities)

    async def get_value(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        age_seconds: int = 120,
    ) -> Any | None:
        """Load data"""
        async with self._sema_get_or_load_value:

            if (
                cached_value := self._get_value_from_cache(
                    channel_address=channel_address,
                    paramset_key=paramset_key,
                    parameter=parameter,
                    age_seconds=age_seconds,
                )
            ) != NO_CACHE_ENTRY:
                return cached_value

            if (
                paramset_key == PARAMSET_KEY_VALUES
                and not self._client.central.device_data.is_empty
            ):
                return None

            if paramset_key not in self._value_cache:
                self._value_cache[paramset_key] = {}
            if channel_address not in self._value_cache[paramset_key]:
                self._value_cache[paramset_key][channel_address] = {}

            try:
                value = await self._client.get_value(
                    channel_address=channel_address,
                    parameter=parameter,
                    paramset_key=paramset_key,
                )
                self._value_cache[paramset_key][channel_address][
                    parameter
                ] = CacheEntry(value=value, last_update=datetime.now())
                return value

            except BaseHomematicException as bhe:
                _LOGGER.debug(
                    "_get_or_load_value: Failed to get cached paramset for %s, %s, %s: %s",
                    self._device.device_type,
                    channel_address,
                    parameter,
                    bhe,
                )

        return None

    def _get_value_from_cache(
        self,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        age_seconds: int,
    ) -> Any | None:
        """Load data"""
        if (
            global_value := self._client.central.device_data.get_device_data(
                interface=self._client.interface,
                channel_address=channel_address,
                parameter=parameter,
            )
        ) is not None:
            return global_value

        if (
            paramset_key == PARAMSET_KEY_VALUES
            and not self._client.central.device_data.is_empty
        ):
            return None

        if (
            cache_entry := self._value_cache.get(paramset_key, {})
            .get(channel_address, {})
            .get(parameter)
        ) is not None:
            if updated_within_seconds(
                last_update=cache_entry.last_update, age_seconds=age_seconds
            ):
                if cache_value := cache_entry.value:
                    return cache_value
        return NO_CACHE_ENTRY


@dataclass
class CacheEntry:
    """An entry for the value cache."""

    value: Any
    last_update: datetime


def _is_binary_sensor(parameter_data: dict[str, Any]) -> bool:
    """Check, if the sensor is a binary_sensor."""
    if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
        return True
    value_list = parameter_data.get("VALUE_LIST")
    if value_list == ["CLOSED", "OPEN"]:
        return True
    if value_list == ["DRY", "RAIN"]:
        return True
    if value_list == ["STABLE", "NOT_STABLE"]:
        return True
    return False
