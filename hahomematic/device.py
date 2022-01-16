"""
Module for the Device class.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    ACCEPT_PARAMETER_ONLY_ON_CHANNEL,
    ATTR_HM_FIRMWARE,
    ATTR_HM_FLAGS,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SUBTYPE,
    ATTR_HM_TYPE,
    BUTTON_ACTIONS,
    CLICK_EVENTS,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    FLAG_INTERAL,
    HH_EVENT_DEVICES_CREATED,
    HM_VIRTUAL_REMOTES,
    IDENTIFIERS_SEPARATOR,
    IGNORED_PARAMETERS,
    IGNORED_PARAMETERS_WILDCARDS_END,
    IGNORED_PARAMETERS_WILDCARDS_START,
    INIT_DATETIME,
    MANUFACTURER,
    OPERATION_EVENT,
    OPERATION_WRITE,
    PARAMSET_VALUES,
    RELEVANT_PARAMSETS,
    SPECIAL_EVENTS,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    WHITELIST_PARAMETERS,
)
from hahomematic.devices import entity_definition_exists, get_device_funcs
from hahomematic.entity import (
    BaseEntity,
    BaseEvent,
    CallbackEntity,
    ClickEvent,
    CustomEntity,
    GenericEntity,
    SpecialEvent,
)
from hahomematic.helpers import generate_unique_id, get_device_channel, get_device_name
from hahomematic.internal.action import HmAction
from hahomematic.internal.text import HmText
from hahomematic.platforms.binary_sensor import HmBinarySensor
from hahomematic.platforms.button import HmButton
from hahomematic.platforms.number import HmFloat, HmInteger
from hahomematic.platforms.select import HmSelect
from hahomematic.platforms.sensor import HmSensor
from hahomematic.platforms.switch import HmSwitch
import hahomematic.support as hm_support

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
        self._client = self._central.clients[self._interface_id]
        self._device_address = device_address
        self._channels = self._central.raw_devices.get_channels(
            self._interface_id, self._device_address
        )
        _LOGGER.debug(
            "Device.__init__: Initializing device: %s, %s",
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
            self._central.raw_devices.get_device_parameter(
                interface_id=self._interface_id,
                device_address=self._device_address,
                parameter=ATTR_HM_TYPE,
            )
        )
        self.sub_type: str = str(
            self._central.raw_devices.get_device_parameter(
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
            self._central.raw_devices.get_device_parameter(
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
        _LOGGER.debug(
            "Device.__init__: Initialized device: %s, %s, %s, %s",
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
        return self._central.rooms.get_room(self._device_address)

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
        if callable(update_callback):
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
    def device_info(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {
            "identifiers": {
                (
                    self._central.domain,
                    f"{self._device_address}{IDENTIFIERS_SEPARATOR}{self._interface_id}",
                )
            },
            "name": self.name,
            "manufacturer": MANUFACTURER,
            "model": self.device_type,
            "sw_version": self.firmware,
            "suggested_area": self.room,
            "via_device": (self._central.domain, self._central.instance_name),
        }

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._available is False:
            return False
        un_reach = self.action_events.get((f"{self._device_address}:0", EVENT_UN_REACH))
        if un_reach is None:
            un_reach = self.action_events.get(
                (f"{self._device_address}:0", EVENT_STICKY_UN_REACH)
            )
        if un_reach is not None and un_reach.value is not None:
            return not un_reach.value
        return True

    def set_availability(self, value: bool) -> None:
        """Set the availability of the device."""
        if not self._available == value:
            self._available = value
            for entity in self.entities.values():
                entity.update_entity()

    async def reload_paramsets(self) -> None:
        """Reload paramset for device."""
        for entity in self.entities.values():
            for paramset in RELEVANT_PARAMSETS:
                await self._client.fetch_paramset(
                    channel_address=entity.channel_address, paramset=paramset
                )
                entity.update_parameter_data()
        self.update_device()

    # pylint: disable=too-many-nested-blocks
    def create_entities(self) -> set[BaseEntity]:
        """
        Create the entities associated to this device.
        """
        new_entities: list[BaseEntity] = []
        for channel_address in self._channels:
            if not self._central.paramsets.get_by_interface_channel_address(
                interface_id=self._interface_id, channel_address=channel_address
            ):
                _LOGGER.debug(
                    "Device.create_entities: Skipping channel %s, missing paramsets.",
                    channel_address,
                )
                continue
            for paramset in self._central.paramsets.get_by_interface_channel_address(
                interface_id=self._interface_id, channel_address=channel_address
            ):
                if paramset != PARAMSET_VALUES:
                    continue
                for (
                    parameter,
                    parameter_data,
                ) in self._central.paramsets.get_by_interface_channel_address_paramset(
                    interface_id=self._interface_id,
                    channel_address=channel_address,
                    paramset=paramset,
                ).items():
                    entity: GenericEntity | None

                    if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT and (
                        parameter in CLICK_EVENTS or parameter in SPECIAL_EVENTS
                    ):
                        self.create_event(
                            channel_address=channel_address,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if self.device_type in HM_VIRTUAL_REMOTES:
                            entity = self.create_action(
                                channel_address=channel_address,
                                parameter=parameter,
                                parameter_data=parameter_data,
                            )
                            if entity is not None:
                                new_entities.append(entity)
                    if (
                        not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT
                        and not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE
                    ) or parameter_data[ATTR_HM_FLAGS] & FLAG_INTERAL:
                        _LOGGER.debug(
                            "Device.create_entities: Skipping %s (no event or internal)",
                            parameter,
                        )
                        continue
                    if not (parameter in CLICK_EVENTS or parameter in SPECIAL_EVENTS):
                        entity = self.create_entity(
                            channel_address=channel_address,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if entity is not None:
                            new_entities.append(entity)
        # create custom entities
        if self.is_custom_entity:
            _LOGGER.debug(
                "Device.create_entities: Handling custom entity integration: %s, %s, %s",
                self._interface_id,
                self._device_address,
                self.device_type,
            )
            # Call the custom creation function.

            for (device_func, group_base_channels) in get_device_funcs(
                self.device_type, self.sub_type
            ):
                custom_entities: list[CustomEntity] = device_func(
                    self, self._device_address, group_base_channels
                )
                new_entities.extend(custom_entities)
        return set(new_entities)

    def create_action(
        self, channel_address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> HmAction | None:
        """Create the actions associated to this device"""
        unique_id = generate_unique_id(
            domain=self._central.domain,
            instance_name=self._central.instance_name,
            address=channel_address,
            parameter=parameter,
            prefix=f"button_{self._central.instance_name}",
        )
        _LOGGER.debug(
            "create_event: Creating action for %s, %s, %s",
            channel_address,
            parameter,
            self._interface_id,
        )

        if action := HmAction(
            device=self,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
        ):
            action.add_to_collections()
            return action
        return None

    def create_event(
        self, channel_address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> BaseEvent | None:
        """Create action event entity."""
        if (channel_address, parameter) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []

        unique_id = generate_unique_id(
            domain=self._central.domain,
            instance_name=self._central.instance_name,
            address=channel_address,
            parameter=parameter,
            prefix=f"event_{self._central.instance_name}",
        )

        _LOGGER.debug(
            "create_event: Creating event for %s, %s, %s",
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
            elif parameter in SPECIAL_EVENTS:
                action_event = SpecialEvent(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if action_event:
            action_event.add_to_collections()
        return action_event

    def create_entity(
        self, channel_address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> GenericEntity | None:
        """
        Helper that looks at the paramsets, decides which default
        platform should be used, and creates the required entities.
        """
        if _ignore_parameter(
            parameter=parameter, channel_no=get_device_channel(channel_address)
        ):
            _LOGGER.debug(
                "create_entity: Ignoring parameter: %s (%s)", parameter, channel_address
            )
            return None
        if (channel_address, parameter) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []

        unique_id = generate_unique_id(
            domain=self._central.domain,
            instance_name=self._central.instance_name,
            address=channel_address,
            parameter=parameter,
        )
        if unique_id in self._central.hm_entities:
            _LOGGER.debug("create_entity: Skipping %s (already exists)", unique_id)
            return None
        _LOGGER.debug(
            "create_entity: Creating entity for %s, %s, %s",
            channel_address,
            parameter,
            self._interface_id,
        )
        entity: GenericEntity | None = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
            if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity: action (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    if parameter in BUTTON_ACTIONS:
                        entity = HmButton(
                            device=self,
                            unique_id=unique_id,
                            channel_address=channel_address,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                    else:
                        entity = HmAction(
                            device=self,
                            unique_id=unique_id,
                            channel_address=channel_address,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                else:
                    _LOGGER.debug(
                        "create_entity: switch (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
            else:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity: action (action): %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmAction(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                    _LOGGER.debug(
                        "create_entity: switch: %s %s", channel_address, parameter
                    )
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                    _LOGGER.debug(
                        "create_entity: select: %s %s", channel_address, parameter
                    )
                    entity = HmSelect(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_FLOAT:
                    _LOGGER.debug(
                        "create_entity: number.integer: %s %s",
                        channel_address,
                        parameter,
                    )
                    entity = HmFloat(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_INTEGER:
                    _LOGGER.debug(
                        "create_entity: number.float: %s %s", channel_address, parameter
                    )
                    entity = HmInteger(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                    # There is currently no entity platform in HA for this.
                    _LOGGER.debug(
                        "create_entity: text: %s %s", channel_address, parameter
                    )
                    entity = HmText(
                        device=self,
                        unique_id=unique_id,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                else:
                    _LOGGER.warning(
                        "unsupported actor: %s %s %s",
                        channel_address,
                        parameter,
                        parameter_data[ATTR_HM_TYPE],
                    )
        else:
            # Also check, if sensor could be a binary_sensor due to value_list.
            if _is_binary_sensor(parameter_data):
                _LOGGER.debug(
                    "create_entity: binary_sensor: %s %s", channel_address, parameter
                )
                entity = HmBinarySensor(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            else:
                _LOGGER.debug(
                    "create_entity: sensor: %s %s", channel_address, parameter
                )
                entity = HmSensor(
                    device=self,
                    unique_id=unique_id,
                    channel_address=channel_address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if entity:
            entity.add_to_collections()
        return entity


def create_devices(central: hm_central.CentralUnit) -> None:
    """
    Trigger creation of the objects that expose the functionality.
    """
    new_devices = set[str]()
    new_entities: list[BaseEntity] = []
    for interface_id, client in central.clients.items():
        if not client:
            _LOGGER.debug(
                "create_devices: Skipping interface %s, missing client.", interface_id
            )
            continue
        if not central.paramsets.get_by_interface(interface_id=interface_id):
            _LOGGER.debug(
                "create_devices: Skipping interface %s, missing paramsets.",
                interface_id,
            )
            continue
        for device_address in central.raw_devices.get_addresses(
            interface_id=interface_id
        ):
            # Do we check for duplicates here? For now, we do.
            device: HmDevice | None = None
            if device_address in central.hm_devices:
                _LOGGER.debug(
                    "create_devices: Skipping device %s on %s, already exists.",
                    device_address,
                    interface_id,
                )
                continue
            try:
                device = HmDevice(
                    central=central,
                    interface_id=interface_id,
                    device_address=device_address,
                )
                new_devices.add(device_address)
                central.hm_devices[device_address] = device
            except Exception:
                _LOGGER.exception(
                    "create_devices: Failed to create device: %s, %s",
                    interface_id,
                    device_address,
                )
            try:
                if device:
                    new_entities.extend(device.create_entities())
            except Exception:
                _LOGGER.exception(
                    "create_devices: Failed to create entities: %s, %s",
                    interface_id,
                    device_address,
                )
    if callable(central.callback_system_event):
        central.callback_system_event(
            HH_EVENT_DEVICES_CREATED, new_devices, set(new_entities)
        )


def _is_binary_sensor(parameter_data: dict[str, Any]) -> bool:
    """Check, if the sensor is a binary_sensor."""
    if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
        return True
    value_list = parameter_data.get("VALUE_LIST")
    if value_list == ["CLOSED", "OPEN"]:
        return True
    if value_list == ["DRY", "RAIN"]:
        return True
    return False


def _ignore_parameter(parameter: str, channel_no: int) -> bool:
    """Check if parameter can be ignored."""
    if parameter in WHITELIST_PARAMETERS:
        return False
    if parameter in IGNORED_PARAMETERS:
        return True
    if parameter.endswith(tuple(IGNORED_PARAMETERS_WILDCARDS_END)):
        return True
    if parameter.startswith(tuple(IGNORED_PARAMETERS_WILDCARDS_START)):
        return True
    if (accept_channel := ACCEPT_PARAMETER_ONLY_ON_CHANNEL.get(parameter)) is not None:
        if accept_channel != channel_no:
            return True

    return False
