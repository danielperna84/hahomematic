"""
Functions for entity creation.
"""

from abc import ABC, abstractmethod
import datetime
import logging
from typing import Any

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_HM_DEFAULT,
    ATTR_HM_FLAGS,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE_LIST,
    ATTR_INTERFACE_ID,
    ATTR_PARAMETER,
    ATTR_TYPE,
    ATTR_VALUE,
    DATA_LOAD_FAIL,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    EVENT_ALARM,
    EVENT_CONFIG_PENDING,
    EVENT_IMPULSE,
    EVENT_KEYPRESS,
    EVENT_UN_REACH,
    FLAG_SERVICE,
    FLAG_VISIBLE,
    HA_PLATFORM_EVENT,
    HIDDEN_PARAMETERS,
    HM_ENTITY_UNIT_REPLACE,
    OPERATION_READ,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
)
from hahomematic.devices.device_description import (
    DD_FIELDS,
    DD_FIELDS_REP,
    get_default_entities,
)
from hahomematic.helpers import get_custom_entity_name, get_entity_name

_LOGGER = logging.getLogger(__name__)


class CallbackEntity(ABC):
    """Base class for callback entities."""

    def __init__(self):
        self.last_update = None
        self._update_callbacks = []
        self._remove_callbacks = []

    def register_update_callback(self, update_callback) -> None:
        """register update callback"""
        if callable(update_callback):
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback) -> None:
        """remove update callback"""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_entity(self, *args) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(*args)

    def register_remove_callback(self, remove_callback) -> None:
        """register remove callback"""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback) -> None:
        """remove remove callback"""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def remove_entity(self, *args) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        for _callback in self._remove_callbacks:
            _callback(*args)

    def _set_last_update(self) -> None:
        self.last_update = datetime.datetime.now()

    def _updated_within_minutes(self, minutes=10) -> bool:
        if self.last_update is None:
            return False
        delta = datetime.datetime.now() - self.last_update
        if delta.seconds < minutes * 60:
            return True
        return False


class BaseEntity(ABC):
    """Base class for regular entities."""

    def __init__(self, device, unique_id, address, platform):
        """
        Initialize the entity.
        """
        self._device = device
        self.unique_id = unique_id
        self.address = address
        self.platform = platform
        self._central = self._device.central
        self._interface_id = self._device.interface_id
        self.device_type = self._device.device_type
        self.create_in_ha = not self._device.is_custom_device
        self.client = self._central.clients[self._interface_id]
        self.proxy = self.client.proxy
        self.name = self.client.central.names_cache.get(self._interface_id, {}).get(
            self.address, self.unique_id
        )

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def device_info(self) -> dict[str, str]:
        """Return device specific attributes."""
        return self._device.device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        return {ATTR_INTERFACE_ID: self._interface_id, ATTR_ADDRESS: self.address}

    def add_to_collections(self) -> None:
        """add entity to central_unit collections"""
        self._device.add_hm_entity(self)
        self._central.hm_entities[self.unique_id] = self

    def __str__(self) -> str:
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self._device.device_type}, name: {self.name}"


class BaseParameterEntity(BaseEntity):
    """
    Base class for stateless entities.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data, platform):
        """
        Initialize the entity.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            platform=platform,
        )

        self.parameter = parameter
        # Do not create some Entities in HA
        if self.parameter in HIDDEN_PARAMETERS:
            self.create_in_ha = False
        self._parameter_data = parameter_data
        self._assign_parameter_data()

        self.name = get_entity_name(
            central=self._central,
            interface_id=self._interface_id,
            address=self.address,
            parameter=self.parameter,
            unique_id=self.unique_id,
        )

    def _assign_parameter_data(self):
        """Assign parameter data to instance variables."""
        self._type = self._parameter_data.get(ATTR_HM_TYPE)
        self._default = self._parameter_data.get(ATTR_HM_DEFAULT)
        flags = self._parameter_data.get(ATTR_HM_FLAGS, 0)
        self._visible = flags & FLAG_VISIBLE == FLAG_VISIBLE
        self._service = flags & FLAG_SERVICE == FLAG_SERVICE
        self._max = self._parameter_data.get(ATTR_HM_MAX)
        self._min = self._parameter_data.get(ATTR_HM_MIN)
        self._operations = self._parameter_data.get(ATTR_HM_OPERATIONS)
        self._special = self._parameter_data.get(ATTR_HM_SPECIAL)
        self._unit = fix_unit(self._parameter_data.get(ATTR_HM_UNIT))
        self._value_list = self._parameter_data.get(ATTR_HM_VALUE_LIST)

    def update_parameter_data(self):
        """Update parameter data"""
        self._assign_parameter_data()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        state_attr = super().extra_state_attributes
        state_attr[ATTR_PARAMETER] = self.parameter
        return state_attr

    @property
    def default(self):
        """Return default value."""
        return self._convert_value(self._default)

    @property
    def min(self):
        """Return min value."""
        return self._convert_value(self._min)

    @property
    def max(self):
        """Return max value."""
        return self._convert_value(self._max)

    @property
    def unit(self):
        """Return unit value."""
        return self._unit

    @property
    def value_list(self):
        """Return the value_list."""
        return self._value_list

    @property
    def hmtype(self):
        """Return the homematic type."""
        return self._type

    def _convert_value(self, value):
        """Convert value to a given hm_type."""
        if self._type == TYPE_BOOL:
            return bool(value)
        if self._type == TYPE_FLOAT:
            return float(value)
        if self._type == TYPE_INTEGER:
            return int(value)
        if self._type == TYPE_STRING:
            return str(value)
        return value

    async def send_value(self, value) -> None:
        """send value to ccu."""
        try:
            await self.proxy.setValue(self.address, self.parameter, value)
        except Exception:
            _LOGGER.exception(
                "generic_entity: Failed to set state for: %s, %s, %s, %s",
                self._device.device_type,
                self.address,
                self.parameter,
                value,
            )


class GenericEntity(BaseParameterEntity, CallbackEntity):
    """
    Base class for generic entities.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data, platform):
        """
        Initialize the entity.
        """
        BaseParameterEntity.__init__(
            self=self,
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=platform,
        )
        CallbackEntity.__init__(self)

        self._state = None
        if self._type == TYPE_ACTION:
            self._state = False

        # Subscribe for all events of this device
        if (
            self.address,
            self.parameter,
        ) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[
                (self.address, self.parameter)
            ] = []
        self._central.entity_event_subscriptions[(self.address, self.parameter)].append(
            self.event
        )

    def event(self, interface_id, address, parameter, value) -> None:
        """
        Handle event for which this entity has subscribed.
        """
        if self._state is value:
            return

        _LOGGER.debug(
            "Entity.event: %s, %s, %s, new: %s, old: %s",
            interface_id,
            address,
            parameter,
            value,
            self._state,
        )
        if interface_id != self._interface_id:
            _LOGGER.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
            )
            return
        if address != self.address:
            _LOGGER.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                address,
                self.address,
            )
            return
        if parameter != self.parameter:
            _LOGGER.warning(
                "Entity.event: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return

        if self._state is not value:
            self._state = value
            self.update_entity(self.unique_id)

    @property
    @abstractmethod
    def state(self):
        """Return the state of the entity."""
        ...

    async def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD
        try:
            if self._operations & OPERATION_READ:
                self._state = await self.proxy.getValue(self.address, self.parameter)
                self.update_entity()

            self.update_entity(self.unique_id)
            return DATA_LOAD_SUCCESS
        except Exception as err:
            _LOGGER.debug(
                " %s: Failed to get state for %s, %s, %s: %s",
                self.platform,
                self._device.device_type,
                self.address,
                self.parameter,
                err,
            )
            return DATA_LOAD_FAIL

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[(self.address, self.parameter)]


class CustomEntity(BaseEntity, CallbackEntity):
    """
    Base class for custom entities.
    """

    def __init__(
        self,
        device,
        unique_id,
        address,
        device_desc,
        entity_desc,
        platform,
        channel_no=None,
    ):
        """
        Initialize the entity.
        """
        BaseEntity.__init__(
            self=self,
            device=device,
            unique_id=unique_id,
            address=address,
            platform=platform,
        )

        CallbackEntity.__init__(self)

        self.create_in_ha = True
        self._device_desc = device_desc
        self._entity_desc = entity_desc
        self._channel_no = channel_no
        self.name = get_custom_entity_name(
            central=self._central,
            interface_id=self._interface_id,
            address=self.address,
            unique_id=self.unique_id,
            channel_no=channel_no,
        )
        self.data_entities: dict[str, GenericEntity] = {}
        self._init_entities()

    def _init_entities(self) -> None:
        """init entity collection"""
        fields_rep = self._device_desc.get(DD_FIELDS_REP, {})
        # Add repeating fields
        for (f_name, p_name) in fields_rep.items():
            f_address = f"{self.address}:{self._channel_no}"
            entity = self._device.get_hm_entity(f_address, p_name)
            self._add_entity(f_name, entity)
        # Add device fields
        fields = self._device_desc.get(DD_FIELDS, {})
        for channel_no, channel in fields.items():
            # if self._channel_no and self._channel_no is not channel_no:
            #     continue
            for f_name, p_name in channel.items():
                f_address = f"{self.address}:{channel_no}"
                entity = self._device.get_hm_entity(f_address, p_name)
                self._add_entity(f_name, entity)
        # add device entities
        self._mark_entity(self._entity_desc)
        # add default entities
        self._mark_entity(get_default_entities())

    def _mark_entity(self, field_desc):
        """Mark entities to be created in HA."""
        if not field_desc:
            return
        for channel_no, field in field_desc.items():
            f_address = f"{self.address}:{channel_no}"
            for p_name in field.values():
                entity = self._device.get_hm_entity(f_address, p_name)
                if entity:
                    entity.create_in_ha = True

    def _add_entity(self, f_name, entity: GenericEntity):
        """Add entity to collection and register callback"""
        if not entity:
            return

        entity.register_update_callback(self.update_entity)
        self.data_entities[f_name] = entity

    def _remove_entity(self, f_name, entity: GenericEntity):
        """Remove entity from collection and un-register callback"""
        if not entity:
            return
        entity.unregister_update_callback(self.update_entity)
        del self.data_entities[f_name]

    async def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD

        for entity in self.data_entities.values():
            if entity:
                await entity.load_data()

        self.update_entity()
        return DATA_LOAD_SUCCESS

    def _get_entity_value(self, field_name, default=None):
        """get entity value"""
        entity = self.data_entities.get(field_name)
        if entity:
            return entity.state
        return default

    def _get_entity_attribute(self, field_name, attr_name, default=None):
        """get entity attribute value"""
        entity = self.data_entities.get(field_name)
        if entity and hasattr(entity, attr_name):
            return getattr(entity, attr_name)
        return default

    async def _send_value(self, field_name, value) -> None:
        """send value to ccu"""
        entity = self.data_entities.get(field_name)
        if entity:
            await entity.send_value(value)


class BaseEvent(BaseParameterEntity):
    """Base class for action events"""

    def __init__(
        self,
        device,
        unique_id,
        address,
        parameter,
        parameter_data,
        event_type,
        platform,
    ):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=platform,
        )

        self.name = get_entity_name(
            central=self._central,
            interface_id=self._interface_id,
            address=self.address,
            parameter=self.parameter,
            unique_id=self.unique_id,
        )
        self.event_type = event_type
        self.last_update = None
        self._value = None

        # Subscribe for all action events of this device
        if (
            self.address,
            self.parameter,
        ) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[
                (self.address, self.parameter)
            ] = []
        self._central.entity_event_subscriptions[(self.address, self.parameter)].append(
            self.event
        )

    def event(self, interface_id, address, parameter, value) -> None:
        """
        Handle event for which this handler has subscribed.
        """
        _LOGGER.debug(
            "Entity.event: %s, %s, %s, %s", interface_id, address, parameter, value
        )
        if interface_id != self._interface_id:
            _LOGGER.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
            )
            return
        if address != self.address:
            _LOGGER.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                address,
                self.address,
            )
            return
        if parameter != self.parameter:
            _LOGGER.warning(
                "Entity.event: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return

        # fire an event
        self.fire_event(value)

    @property
    def value(self):
        """Return the value."""
        return self._value

    async def send_value(self, value) -> None:
        """Send value to ccu."""
        try:
            await self.proxy.setValue(self.address, self.parameter, value)
        except Exception:
            _LOGGER.exception(
                "action_event: Failed to set state for: %s, %s, %s",
                self.address,
                self.parameter,
                value,
            )

    def add_to_collections(self) -> None:
        """Add entity to central_unit collections."""
        self._device.add_hm_action_event(self)

    def _set_last_update(self) -> None:
        self.last_update = datetime.datetime.now()

    @abstractmethod
    def get_event_data(self, value=None):
        """Get the event_data."""

    @abstractmethod
    def fire_event(self, value) -> None:
        """
        Do what is needed to fire an event.
        """

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[(self.address, self.parameter)]


class AlarmEvent(BaseEvent):
    """
    class for handling alarm events.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            event_type=EVENT_ALARM,
            platform=HA_PLATFORM_EVENT,
        )

    def get_event_data(self, value=None):
        """Get the event_data."""
        address = self.address.split(":")[0]
        click_type = self.parameter.lower()
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: address,
            ATTR_TYPE: click_type,
        }

    def fire_event(self, value) -> None:
        """
        Do what is needed to fire an event.
        """
        if self._value == value and value is False:
            return

        self._set_last_update()
        self._value = value

        if callable(self._central.callback_alarm_event):
            self._central.callback_alarm_event(
                self.event_type,
                self.get_event_data(value),
            )


class ClickEvent(BaseEvent):
    """
    class for handling click events.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            event_type=EVENT_KEYPRESS,
            platform=HA_PLATFORM_EVENT,
        )

    def get_event_data(self, value=None):
        """Get the event_data."""
        (address, channel_no) = self.address.split(":")
        click_type = f"channel_{channel_no}_{self.parameter}".lower()
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: address,
            ATTR_TYPE: click_type,
        }

    def fire_event(self, value) -> None:
        """
        Do what is needed to fire an event.
        """
        if callable(self._central.callback_click_event):
            self._central.callback_click_event(
                self.event_type,
                self.get_event_data(),
            )


class ImpulseEvent(BaseEvent):
    """
    class for handling impulse events.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            event_type=EVENT_IMPULSE,
            platform=HA_PLATFORM_EVENT,
        )

    def get_event_data(self, value=None):
        """Get the event_data."""
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: self.address,
            ATTR_PARAMETER: self.parameter,
            ATTR_VALUE: value,
        }

    def fire_event(self, value) -> None:
        """
        Do what is needed to fire an event.
        """
        if self._value == value:
            return
        old_value = self._value
        self._set_last_update()
        self._value = value

        if self.parameter == EVENT_CONFIG_PENDING:
            if value is False and old_value is True:
                self.client.central.create_task(self._device.reload_paramsets())
            return
        if self.parameter == EVENT_UN_REACH:
            self._device.update_device(self.unique_id)
            return

        if callable(self._central.callback_impulse_event):
            self._central.callback_impulse_event(
                self.event_type,
                self.get_event_data(value),
            )


def fix_unit(unit):
    """replace given unit"""
    if not unit:
        return None
    for (check, fix) in HM_ENTITY_UNIT_REPLACE.items():
        if check in unit:
            return fix
    return unit
