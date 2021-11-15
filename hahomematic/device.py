# pylint: disable=line-too-long

"""
Module for the Device class
"""
import datetime
import logging
from typing import Optional

from hahomematic.action_event import AlarmEvent, BaseEvent, ClickEvent, ImpulseEvent
from hahomematic.const import (
    ALARM_EVENTS,
    ATTR_HM_FIRMWARE,
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    CLICK_EVENTS,
    HA_DOMAIN,
    HH_EVENT_DEVICES_CREATED,
    IGNORED_PARAMETERS,
    IGNORED_PARAMETERS_WILDCARDS,
    IMPULSE_EVENTS,
    OPERATION_EVENT,
    OPERATION_WRITE,
    PARAM_UN_REACH,
    PARAMSET_VALUES,
    RELEVANT_PARAMSETS,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    WHITELIST_PARAMETERS,
    WRITE_ACTIONS,
)
from hahomematic.devices import device_desc_exists, get_device_funcs
from hahomematic.entity import BaseEntity, CustomEntity, GenericEntity
from hahomematic.helpers import generate_unique_id
from hahomematic.internal.action import HmAction
from hahomematic.internal.text import HmText
from hahomematic.platforms.binary_sensor import HmBinarySensor
from hahomematic.platforms.number import HmNumber
from hahomematic.platforms.select import HmSelect
from hahomematic.platforms.sensor import HmSensor
from hahomematic.platforms.switch import HmSwitch

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class HmDevice:
    """
    Object to hold information about a device and associated entities.
    """

    def __init__(self, server, interface_id, address):
        """
        Initialize the device object.
        """
        self.server = server
        self.interface_id = interface_id
        self.client = self.server.clients[self.interface_id]
        self.address = address
        self.channels = self.server.devices[self.interface_id][self.address]
        _LOGGER.debug(
            "Device.__init__: Initializing device: %s, %s",
            self.interface_id,
            self.address,
        )

        self.entities: dict[tuple[str, str], GenericEntity] = {}
        self.custom_entities: dict[str, CustomEntity] = {}
        self.action_events: dict[tuple[str, str], BaseEvent] = {}
        self.last_update = None
        self._update_callbacks = []
        self._remove_callbacks = []
        self.device_type = self.server.devices_raw_dict[self.interface_id][
            self.address
        ][ATTR_HM_TYPE]
        # marker if device will be created as custom device
        self.is_custom_device = device_desc_exists(self.device_type)
        self.firmware = self.server.devices_raw_dict[self.interface_id][self.address][
            ATTR_HM_FIRMWARE
        ]
        if self.address in self.server.names_cache.get(self.interface_id, {}):
            self.name = self.server.names_cache[self.interface_id][self.address]
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

    def add_hm_entity(self, hm_entity: BaseEntity):
        """add an hm entity to a device"""
        if isinstance(hm_entity, GenericEntity):
            hm_entity.register_update_callback(self.update_device)
            hm_entity.register_remove_callback(self.remove_device)
            self.entities[(hm_entity.address, hm_entity.parameter)] = hm_entity
        elif isinstance(hm_entity, CustomEntity):
            self.custom_entities[hm_entity.unique_id] = hm_entity

    def remove_hm_entity(self, hm_entity: BaseEntity):
        """add an hm entity to a device"""
        if isinstance(hm_entity, GenericEntity):
            hm_entity.unregister_update_callback(self.update_device)
            hm_entity.unregister_remove_callback(self.remove_device)
            del self.entities[(hm_entity.address, hm_entity.parameter)]
        elif isinstance(hm_entity, CustomEntity):
            del self.custom_entities[hm_entity.unique_id]

    def add_hm_action_event(self, hm_event: BaseEvent):
        """add an hm entity to a device"""
        self.action_events[(hm_event.address, hm_event.parameter)] = hm_event

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        for entity in self.entities.values():
            entity.remove_event_subscriptions()
        for action_event in self.action_events.values():
            action_event.remove_event_subscriptions()

    def register_update_callback(self, update_callback) -> None:
        """register update callback"""
        if callable(update_callback):
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback) -> None:
        """remove update callback"""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_device(self, *args) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            # pylint: disable=not-callable
            _callback(*args)

    def register_remove_callback(self, remove_callback) -> None:
        """register remove callback"""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback) -> None:
        """remove remove callback"""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def remove_device(self, *args) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        for _callback in self._remove_callbacks:
            # pylint: disable=not-callable
            _callback(*args)

    def _set_last_update(self) -> None:
        self.last_update = datetime.datetime.now()

    def get_hm_entity(self, address, parameter) -> Optional[GenericEntity]:
        """return a hm_entity from device"""
        return self.entities.get((address, parameter))

    def __str__(self):
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "config_entry_id": self.server.entry_id,
            "identifiers": {(HA_DOMAIN, self.address)},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": self.device_type,
            "sw_version": self.firmware,
            "via_device": (HA_DOMAIN, self.interface_id),
        }

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        un_reach = self.action_events.get((f"{self.address}:0", PARAM_UN_REACH))
        if un_reach and un_reach.last_update:
            return not un_reach.value
        return True

    def reload_paramsets(self) -> None:
        """Reload paramset for device."""
        for entity in self.entities.values():
            for paramset in RELEVANT_PARAMSETS:
                self.client.fetch_paramset(entity.address, paramset)
                entity.update_parameter_data()
        self.update_device()

    def create_entities(self) -> Optional[set[GenericEntity]]:
        """
        Create the entities associated to this device.
        """
        new_entities: set[GenericEntity] = set()
        for channel in self.channels:
            if channel not in self.server.paramsets_cache[self.interface_id]:
                _LOGGER.debug(
                    "Device.create_entities: Skipping channel %s, missing paramsets.",
                    channel,
                )
                continue
            for paramset in self.server.paramsets_cache[self.interface_id][channel]:
                if paramset != PARAMSET_VALUES:
                    continue
                for parameter, parameter_data in self.server.paramsets_cache[
                    self.interface_id
                ][channel][paramset].items():
                    if not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
                        if parameter not in WRITE_ACTIONS:
                            _LOGGER.debug(
                                "Device.create_entities: Skipping %s (no event)",
                                parameter,
                            )
                            continue
                    if (
                        parameter in ALARM_EVENTS
                        or parameter in CLICK_EVENTS
                        or parameter in IMPULSE_EVENTS
                    ):
                        self.create_event(
                            address=channel,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                    if not (parameter in CLICK_EVENTS or parameter in IMPULSE_EVENTS):
                        entity = self.create_entity(
                            address=channel,
                            parameter=parameter,
                            parameter_data=parameter_data,
                        )
                        if entity is not None:
                            new_entities.add(entity)
        # create custom entities
        if self.is_custom_device:
            _LOGGER.debug(
                "Device.create_entities: Handling custom device integration: %s, %s, %s",
                self.interface_id,
                self.address,
                self.device_type,
            )
            # Call the custom device / entity creation function.

            for device_func in get_device_funcs(self.device_type):
                custom_entities = device_func(self, self.address)
                new_entities.update(custom_entities)
        return new_entities

    def create_event(self, address, parameter, parameter_data) -> Optional[BaseEvent]:
        if (address, parameter) not in self.server.entity_event_subscriptions:
            self.server.entity_event_subscriptions[(address, parameter)] = []

        unique_id = generate_unique_id(address, parameter, "event")

        _LOGGER.debug(
            "create_event: Creating action_event for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )
        action_event = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
            # if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
            if parameter in CLICK_EVENTS:
                action_event = ClickEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                )
            elif parameter in IMPULSE_EVENTS:
                action_event = ImpulseEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                )
            elif parameter in ALARM_EVENTS:
                action_event = AlarmEvent(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                )
        if action_event:
            action_event.add_to_collections()
        return action_event

    def create_entity(
        self, address, parameter, parameter_data
    ) -> Optional[GenericEntity]:
        """
        Helper that looks at the paramsets, decides which default
        platform should be used, and creates the required entities.
        """
        if (
            parameter in IGNORED_PARAMETERS
            or parameter.endswith(tuple(IGNORED_PARAMETERS_WILDCARDS))
            and parameter not in WHITELIST_PARAMETERS
        ):
            _LOGGER.debug(
                "create_entity: Ignoring parameter: %s (%s)", parameter, address
            )
            return None
        if (address, parameter) not in self.server.entity_event_subscriptions:
            self.server.entity_event_subscriptions[(address, parameter)] = []

        unique_id = generate_unique_id(address, parameter)
        if unique_id in self.server.hm_entities:
            _LOGGER.debug("create_entity: Skipping %s (already exists)", unique_id)
            return None
        _LOGGER.debug(
            "create_entity: Creating entity for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )
        entity = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
            if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
                if parameter in WRITE_ACTIONS:
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
                if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
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


# pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
def create_devices(server) -> None:
    """
    Trigger creation of the objects that expose the functionality.
    """
    new_devices = set[str]()
    new_entities = set[GenericEntity]()
    for interface_id, client in server.clients.items():
        if not client:
            _LOGGER.warning(
                "create_devices: Skipping interface %s, missing client.", interface_id
            )
            continue
        if interface_id not in server.paramsets_cache:
            _LOGGER.warning(
                "create_devices: Skipping interface %s, missing paramsets.",
                interface_id,
            )
            continue
        for device_address in server.devices[interface_id]:
            # Do we check for duplicates here? For now we do.
            device = None
            if device_address in server.hm_devices:
                _LOGGER.debug(
                    "create_devices: Skipping device %s on %s, already exists.",
                    device_address,
                    interface_id,
                )
                continue
            try:
                device = HmDevice(server, interface_id, device_address)
                new_devices.add(device_address)
                server.hm_devices[device_address] = device
            except Exception:
                _LOGGER.exception(
                    "create_devices: Failed to create device: %s, %s",
                    interface_id,
                    device_address,
                )
            try:
                new_entities.update(device.create_entities())
            except Exception as err:
                _LOGGER.exception(
                    "create_devices: Failed to create entities: %s, %s",
                    interface_id,
                    device_address,
                )
    if callable(server.callback_system_event):
        # pylint: disable=not-callable
        server.callback_system_event(
            HH_EVENT_DEVICES_CREATED, new_devices, new_entities
        )


def _is_binary_sensor(parameter_data) -> bool:
    """Check, if the sensor is a binary_sensor."""
    if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
        return True
    value_list = parameter_data.get("VALUE_LIST")
    if value_list == ["CLOSED", "OPEN"]:
        return True
    return False
