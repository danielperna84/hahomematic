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
    ALARM_EVENTS,
    ATTR_HM_FIRMWARE,
    ATTR_HM_FLAGS,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SUBTYPE,
    ATTR_HM_TYPE,
    CLICK_EVENTS,
    FLAG_INTERAL,
    HA_DOMAIN,
    HH_EVENT_DEVICES_CREATED,
    HM_VIRTUAL_REMOTES,
    IDENTIFIERS_SEPARATOR,
    IGNORED_PARAMETERS,
    IGNORED_PARAMETERS_WILDCARDS_END,
    IGNORED_PARAMETERS_WILDCARDS_START,
    INIT_DATETIME,
    OPERATION_EVENT,
    OPERATION_WRITE,
    PARAM_UN_REACH,
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
    AlarmEvent,
    BaseEntity,
    BaseEvent,
    CallbackEntity,
    ClickEvent,
    CustomEntity,
    GenericEntity,
    SpecialEvent,
)
from hahomematic.helpers import generate_unique_id
from hahomematic.internal.action import HmAction
from hahomematic.internal.text import HmText
from hahomematic.platforms.binary_sensor import HmBinarySensor
from hahomematic.platforms.button import HmButton
from hahomematic.platforms.number import HmNumber
from hahomematic.platforms.select import HmSelect
from hahomematic.platforms.sensor import HmSensor
from hahomematic.platforms.switch import HmSwitch

_LOGGER = logging.getLogger(__name__)


class HmDevice:
    """
    Object to hold information about a device and associated entities.
    """

    def __init__(
        self, central: hm_central.CentralUnit, interface_id: str, address: str
    ):
        """
        Initialize the device object.
        """
        self.central = central
        self.interface_id = interface_id
        self.client = self.central.clients[self.interface_id]
        self.address = address
        self.channels = self.central.raw_devices.get_channels(
            self.interface_id, self.address
        )
        _LOGGER.debug(
            "Device.__init__: Initializing device: %s, %s",
            self.interface_id,
            self.address,
        )

        self.entities: dict[tuple[str, str], GenericEntity] = {}
        self.custom_entities: dict[str, CustomEntity] = {}
        self.action_events: dict[tuple[str, str], BaseEvent] = {}
        self.last_update: datetime = INIT_DATETIME
        self._available: bool = True
        self._update_callbacks: list[Callable] = []
        self._remove_callbacks: list[Callable] = []
        self.device_type: str = str(
            self.central.raw_devices.get_device_parameter(
                self.interface_id, self.address, ATTR_HM_TYPE
            )
        )
        self.sub_type: str = str(
            self.central.raw_devices.get_device_parameter(
                self.interface_id, self.address, ATTR_HM_SUBTYPE
            )
        )
        # marker if device will be created as custom entity
        self.is_custom_entity: bool = entity_definition_exists(
            self.device_type, self.sub_type
        )
        self.firmware: str = str(
            self.central.raw_devices.get_device_parameter(
                self.interface_id, self.address, ATTR_HM_FIRMWARE
            )
        )

        if name := self.central.names.get_name(self.address):
            self.name = name
        else:
            _LOGGER.info(
                "Device.__init__: Using auto-generated name for %s %s",
                self.device_type,
                self.address,
            )
            self.name = f"{self.device_type}_{self.address}"

        _LOGGER.debug(
            "Device.__init__: Initialized device: %s, %s, %s, %s",
            self.interface_id,
            self.address,
            self.device_type,
            self.name,
        )

    def add_hm_entity(self, hm_entity: BaseEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(hm_entity, GenericEntity):
            hm_entity.register_update_callback(self.update_device)
            hm_entity.register_remove_callback(self.remove_device)
            self.entities[(hm_entity.address, hm_entity.parameter)] = hm_entity
        if isinstance(hm_entity, CustomEntity):
            self.custom_entities[hm_entity.unique_id] = hm_entity

    def remove_hm_entity(self, hm_entity: CallbackEntity) -> None:
        """Add a hm entity to a device."""
        if isinstance(hm_entity, GenericEntity):
            hm_entity.unregister_update_callback(self.update_device)
            hm_entity.unregister_remove_callback(self.remove_device)
            del self.entities[(hm_entity.address, hm_entity.parameter)]
        if isinstance(hm_entity, CustomEntity):
            del self.custom_entities[hm_entity.unique_id]

    def add_hm_action_event(self, hm_event: BaseEvent) -> None:
        """Add a hm entity to a device."""
        self.action_events[(hm_event.address, hm_event.parameter)] = hm_event

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions."""
        for entity in self.entities.values():
            if isinstance(entity, GenericEntity):
                entity.remove_event_subscriptions()
        for action_event in self.action_events.values():
            action_event.remove_event_subscriptions()

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

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """Register the remove callback."""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """Remove the remove callback."""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def remove_device(self, *args: Any) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        for _callback in self._remove_callbacks:
            _callback(*args)

    def _set_last_update(self) -> None:
        self.last_update = datetime.now()

    def get_hm_entity(self, address: str, parameter: str) -> GenericEntity | None:
        """Return a hm_entity from device."""
        return self.entities.get((address, parameter))

    def __str__(self) -> str:
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}"

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return {
            "config_entry_id": self.central.entry_id,
            "identifiers": {(HA_DOMAIN, f"{self.interface_id}{IDENTIFIERS_SEPARATOR}{self.address}")},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": self.device_type,
            "sw_version": self.firmware,
            "via_device": (HA_DOMAIN, self.central.instance_name),
        }

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        if self._available is False:
            return False
        un_reach = self.action_events.get((f"{self.address}:0", PARAM_UN_REACH))
        if un_reach and un_reach.last_update:
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
                await self.client.fetch_paramset(entity.address, paramset)
                entity.update_parameter_data()
        self.update_device()

    # pylint: disable=too-many-nested-blocks
    def create_entities(self) -> set[BaseEntity]:
        """
        Create the entities associated to this device.
        """
        new_entities: list[BaseEntity] = []
        for channel in self.channels:
            if not self.central.paramsets.get_by_interface_address(
                self.interface_id, channel
            ):
                _LOGGER.debug(
                    "Device.create_entities: Skipping channel %s, missing paramsets.",
                    channel,
                )
                continue
            for paramset in self.central.paramsets.get_by_interface_address(
                self.interface_id, channel
            ):
                if paramset != PARAMSET_VALUES:
                    continue
                for (
                    parameter,
                    parameter_data,
                ) in self.central.paramsets.get_by_interface_address_paramset(
                    self.interface_id, channel, paramset
                ).items():
                    entity: GenericEntity | None
                    if (
                        not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT
                        and not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE
                    ) or parameter_data[ATTR_HM_FLAGS] & FLAG_INTERAL:
                        _LOGGER.debug(
                            "Device.create_entities: Skipping %s (no event or internal)",
                            parameter,
                        )
                        continue
                    if (
                        parameter in ALARM_EVENTS
                        or parameter in CLICK_EVENTS
                        or parameter in SPECIAL_EVENTS
                    ):
                        self.create_event(
                            address=channel,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if self.address.startswith(tuple(HM_VIRTUAL_REMOTES)):
                            entity = self.create_button(
                                address=channel,
                                parameter=parameter,
                                parameter_data=parameter_data,
                            )
                            if entity is not None:
                                new_entities.append(entity)
                    if not (parameter in CLICK_EVENTS or parameter in SPECIAL_EVENTS):
                        entity = self.create_entity(
                            address=channel,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if entity is not None:
                            new_entities.append(entity)
        # create custom entities
        if self.is_custom_entity:
            _LOGGER.debug(
                "Device.create_entities: Handling custom entity integration: %s, %s, %s",
                self.interface_id,
                self.address,
                self.device_type,
            )
            # Call the custom creation function.

            for (device_func, group_base_channels) in get_device_funcs(
                self.device_type, self.sub_type
            ):
                custom_entities: list[CustomEntity] = device_func(
                    self, self.address, group_base_channels
                )
                new_entities.extend(custom_entities)
        return set(new_entities)

    def create_button(
        self, address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> HmButton | None:
        """Create the buttons associated to this device"""
        unique_id = generate_unique_id(
            address, parameter, f"button_{self.central.instance_name}"
        )
        _LOGGER.debug(
            "create_event: Creating button for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )

        if button := HmButton(
            device=self,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
        ):
            button.add_to_collections()
            return button
        return None

    def create_event(
        self, address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> BaseEvent | None:
        """Create action event entity."""
        if (address, parameter) not in self.central.entity_event_subscriptions:
            self.central.entity_event_subscriptions[(address, parameter)] = []

        unique_id = generate_unique_id(
            address, parameter, f"event_{self.central.instance_name}"
        )

        _LOGGER.debug(
            "create_event: Creating event for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )
        action_event: BaseEvent | None = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
            if parameter in CLICK_EVENTS:
                action_event = ClickEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            elif parameter in SPECIAL_EVENTS:
                action_event = SpecialEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            elif parameter in ALARM_EVENTS:
                action_event = AlarmEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if action_event:
            action_event.add_to_collections()
        return action_event

    def create_entity(
        self, address: str, parameter: str, parameter_data: dict[str, Any]
    ) -> GenericEntity | None:
        """
        Helper that looks at the paramsets, decides which default
        platform should be used, and creates the required entities.
        """
        if (
            parameter in IGNORED_PARAMETERS
            or parameter.endswith(tuple(IGNORED_PARAMETERS_WILDCARDS_END))
            or parameter.startswith(tuple(IGNORED_PARAMETERS_WILDCARDS_START))
        ) and parameter not in WHITELIST_PARAMETERS:
            _LOGGER.debug(
                "create_entity: Ignoring parameter: %s (%s)", parameter, address
            )
            return None
        if (address, parameter) not in self.central.entity_event_subscriptions:
            self.central.entity_event_subscriptions[(address, parameter)] = []

        unique_id = generate_unique_id(address, parameter)
        if unique_id in self.central.hm_entities:
            _LOGGER.debug("create_entity: Skipping %s (already exists)", unique_id)
            return None
        _LOGGER.debug(
            "create_entity: Creating entity for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )
        entity: GenericEntity | None = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
            if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity: action (action): %s %s", address, parameter
                    )
                    entity = HmAction(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                else:
                    _LOGGER.debug(
                        "create_entity: switch (action): %s %s", address, parameter
                    )
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
            else:
                if parameter_data[ATTR_HM_OPERATIONS] == OPERATION_WRITE:
                    _LOGGER.debug(
                        "create_entity: action (action): %s %s", address, parameter
                    )
                    entity = HmAction(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                    _LOGGER.debug("create_entity: switch: %s %s", address, parameter)
                    entity = HmSwitch(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                    _LOGGER.debug("create_entity: select: %s %s", address, parameter)
                    entity = HmSelect(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER]:
                    _LOGGER.debug("create_entity: number: %s %s", address, parameter)
                    entity = HmNumber(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                    # There is currently no entity platform in HA for this.
                    _LOGGER.debug("create_entity: text: %s %s", address, parameter)
                    entity = HmText(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                else:
                    _LOGGER.warning(
                        "unsupported actor: %s %s %s",
                        address,
                        parameter,
                        parameter_data[ATTR_HM_TYPE],
                    )
        else:
            # Also check, if sensor could be a binary_sensor due to value_list.
            if _is_binary_sensor(parameter_data):
                _LOGGER.debug("create_entity: binary_sensor: %s %s", address, parameter)
                entity = HmBinarySensor(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            else:
                _LOGGER.debug("create_entity: sensor: %s %s", address, parameter)
                entity = HmSensor(
                    device=self,
                    unique_id=unique_id,
                    address=address,
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
            _LOGGER.warning(
                "create_devices: Skipping interface %s, missing client.", interface_id
            )
            continue
        if not central.paramsets.get_by_interface(interface_id):
            _LOGGER.warning(
                "create_devices: Skipping interface %s, missing paramsets.",
                interface_id,
            )
            continue
        for device_address in central.raw_devices.get_addresses(interface_id):
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
                device = HmDevice(central, interface_id, device_address)
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
    return False
