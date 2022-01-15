"""
Functions for entity creation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, Generic, TypeVar, Union, cast

import hahomematic.central_unit as hm_central
import hahomematic.client as hm_client
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_ENTITY_TYPE,
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
    ATTR_SUBTYPE,
    ATTR_TYPE,
    ATTR_VALUE,
    DATA_LOAD_FAIL,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    FLAG_SERVICE,
    FLAG_VISIBLE,
    HIDDEN_PARAMETERS,
    HM_ENTITY_UNIT_REPLACE,
    INIT_DATETIME,
    OPERATION_READ,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    HmEntityType,
    HmEntityUsage,
    HmEventType,
    HmPlatform,
)
import hahomematic.device as hm_device
import hahomematic.devices as hm_custom_entity
import hahomematic.devices.entity_definition as hm_entity_definition
from hahomematic.helpers import (
    check_channel_is_only_primary_channel,
    get_custom_entity_name,
    get_device_address,
    get_device_channel,
    get_entity_name,
    get_event_name,
)

_LOGGER = logging.getLogger(__name__)
ParameterType = TypeVar("ParameterType", bool, int, float, str, Union[int, str], None)


class CallbackEntity(ABC):
    """Base class for callback entities."""

    def __init__(self) -> None:
        self.last_update: datetime = INIT_DATETIME
        self._update_callbacks: list[Callable] = []
        self._remove_callbacks: list[Callable] = []

    def register_update_callback(self, update_callback: Callable) -> None:
        """register update callback"""
        if callable(update_callback):
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """remove update callback"""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_entity(self, *args: Any) -> None:
        """
        Do what is needed when the value of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(*args)

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """register the remove callback"""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """remove the remove callback"""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def remove_entity(self, *args: Any) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        for _callback in self._remove_callbacks:
            _callback(*args)

    def _set_last_update(self) -> None:
        self.last_update = datetime.now()

    def _updated_within_minutes(self, minutes: int = 10) -> bool:
        delta = datetime.now() - self.last_update
        if delta.seconds < minutes * 60:
            return True
        return False


class BaseEntity(ABC):
    """Base class for regular entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        device_address: str,
        channel_no: int,
        platform: HmPlatform,
    ):
        """
        Initialize the entity.
        """
        self._device = device
        self.unique_id = unique_id
        self._device_address = device_address
        self._channel_no = channel_no
        self.platform = platform
        self._central: hm_central.CentralUnit = self._device.central
        self._interface_id: str = self._device.interface_id
        self.device_type: str = self._device.device_type
        self.sub_type: str = self._device.sub_type
        self.usage: HmEntityUsage = (
            HmEntityUsage.ENTITY_NO_CREATE
            if self._device.is_custom_entity
            else HmEntityUsage.ENTITY
        )
        self._client: hm_client.Client = self._central.clients[self._interface_id]
        self.name: str = (
            self._central.names.get_name(self.channel_address) or self.unique_id
        )

    @property
    def device_address(self) -> str:
        """Return the device address."""
        return self._device_address

    @property
    def channel_address(self) -> str:
        """Return the channel address."""
        return f"{self._device_address}:{self._channel_no}"

    @property
    def channel_no(self) -> int:
        """Return the channel address."""
        return self._channel_no

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._device.available

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device specific attributes."""
        return self._device.device_info

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: self.channel_address,
        }

    def add_to_collections(self) -> None:
        """add entity to central_unit collections"""
        self._device.add_hm_entity(self)
        self._central.hm_entities[self.unique_id] = self

    def __str__(self) -> str:
        """
        Provide some useful information.
        """
        return f"address: {self.channel_address}, type: {self._device.device_type}, name: {self.name}"


class BaseParameterEntity(Generic[ParameterType], BaseEntity):
    """
    Base class for stateless entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
        platform: HmPlatform,
    ):
        """
        Initialize the entity.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            device_address=get_device_address(channel_address),
            channel_no=get_device_channel(channel_address),
            platform=platform,
        )

        self.parameter: str = parameter
        # Do not create some Entities in HA
        if self.parameter in HIDDEN_PARAMETERS:
            self.usage = HmEntityUsage.ENTITY_NO_CREATE
        self._parameter_data = parameter_data
        self._assign_parameter_data()

        self.name = get_entity_name(
            central=self._central,
            channel_address=self.channel_address,
            parameter=self.parameter,
            unique_id=self.unique_id,
            device_type=self.device_type,
        )

    def _assign_parameter_data(self) -> None:
        """Assign parameter data to instance variables."""
        self._type: str = self._parameter_data[ATTR_HM_TYPE]
        self._value_list: list[str] | None = self._parameter_data.get(
            ATTR_HM_VALUE_LIST
        )
        self._default: ParameterType = self._convert_value(
            self._parameter_data[ATTR_HM_DEFAULT]
        )
        self._max: ParameterType = self._convert_value(
            self._parameter_data[ATTR_HM_MAX]
        )
        self._min: ParameterType = self._convert_value(
            self._parameter_data[ATTR_HM_MIN]
        )
        flags: int = self._parameter_data[ATTR_HM_FLAGS]
        self._visible: bool = flags & FLAG_VISIBLE == FLAG_VISIBLE
        self._service: bool = flags & FLAG_SERVICE == FLAG_SERVICE
        self._operations: int = self._parameter_data[ATTR_HM_OPERATIONS]
        self._special: dict[str, Any] | None = self._parameter_data.get(ATTR_HM_SPECIAL)
        self._unit: str | None = fix_unit(self._parameter_data.get(ATTR_HM_UNIT))

    def update_parameter_data(self) -> None:
        """Update parameter data"""
        self._assign_parameter_data()

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        state_attr = super().attributes
        state_attr[ATTR_PARAMETER] = self.parameter
        return state_attr

    @property
    def default(self) -> ParameterType:
        """Return default value."""
        return self._default

    @property
    def min(self) -> ParameterType:
        """Return min value."""
        return self._min

    @property
    def max(self) -> ParameterType:
        """Return max value."""
        return self._max

    @property
    def unit(self) -> str | None:
        """Return unit value."""
        return self._unit

    @property
    def value_list(self) -> list[str] | None:
        """Return the value_list."""
        return self._value_list

    @property
    def hmtype(self) -> str:
        """Return the homematic type."""
        return self._type

    @property
    def visible(self) -> bool:
        """Return the if entity is visible in ccu."""
        return self._visible

    def _convert_value(self, value: ParameterType) -> ParameterType:
        """Convert to value to ParameterType"""
        if value is None:
            return None
        if self._type == TYPE_BOOL:
            return bool(value)  # type: ignore[return-value]
        if self._type == TYPE_FLOAT:
            return float(value)  # type: ignore[return-value]
        if self._type == TYPE_INTEGER:
            return int(float(value))  # type: ignore[return-value]
        if self._type == TYPE_STRING:
            return str(value)  # type: ignore[return-value]
        return value

    async def send_value(self, value: Any) -> None:
        """send value to ccu."""
        try:
            await self._client.set_value(
                channel_address=self.channel_address,
                parameter=self.parameter,
                value=self._convert_value(value),
            )
        except Exception:
            _LOGGER.exception(
                "generic_entity: Failed to set state for: %s, %s, %s, %s",
                self._device.device_type,
                self.channel_address,
                self.parameter,
                value,
            )


class GenericEntity(BaseParameterEntity[ParameterType], CallbackEntity):
    """
    Base class for generic entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
        platform: HmPlatform,
    ):
        """
        Initialize the entity.
        """
        BaseParameterEntity.__init__(
            self=self,
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=platform,
        )
        CallbackEntity.__init__(self)
        self._value: ParameterType | None = None

        # Subscribe for all events of this device
        if (
            self.channel_address,
            self.parameter,
        ) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[
                (self.channel_address, self.parameter)
            ] = []
        self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ].append(self.event)

    def event(
        self, interface_id: str, channel_address: str, parameter: str, raw_value: Any
    ) -> None:
        """
        Handle event for which this entity has subscribed.
        """
        value = self._convert_value(raw_value)
        if self._value is value:
            return

        _LOGGER.debug(
            "Entity.event: %s, %s, %s, new: %s, old: %s",
            interface_id,
            channel_address,
            parameter,
            value,
            self._value,
        )
        if interface_id != self._interface_id:
            _LOGGER.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
            )
            return
        if channel_address != self.channel_address:
            _LOGGER.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                channel_address,
                self.channel_address,
            )
            return
        if parameter != self.parameter:
            _LOGGER.warning(
                "Entity.event: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return

        if self._value is not value:
            self._value = value
            self.update_entity(self.unique_id)

    @property
    def value(self) -> ParameterType | None:
        """Return the value of the entity."""
        return self._value

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the generic entity."""
        state_attr = super().attributes
        state_attr[ATTR_ENTITY_TYPE] = HmEntityType.GENERIC.value
        return state_attr

    async def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD
        try:
            if self._operations & OPERATION_READ:
                self._value = self._convert_value(
                    await self._client.get_value(
                        channel_address=self.channel_address, parameter=self.parameter
                    )
                )
                self.update_entity()

            self.update_entity(self.unique_id)
            return DATA_LOAD_SUCCESS
        except Exception as err:
            _LOGGER.debug(
                " %s: Failed to get value for %s, %s, %s: %s",
                self.platform,
                self._device.device_type,
                self.channel_address,
                self.parameter,
                err,
            )
            return DATA_LOAD_FAIL

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ]


_EntityType = TypeVar("_EntityType", bound=GenericEntity)


class CustomEntity(BaseEntity, CallbackEntity):
    """
    Base class for custom entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        device_address: str,
        device_enum: hm_entity_definition.EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int, set[str]],
        platform: HmPlatform,
        channel_no: int,
    ):
        """
        Initialize the entity.
        """
        BaseEntity.__init__(
            self=self,
            device=device,
            unique_id=unique_id,
            device_address=device_address,
            channel_no=channel_no,
            platform=platform,
        )

        CallbackEntity.__init__(self)

        self._device_enum = device_enum
        self._device_desc = device_def
        self._entity_def = entity_def
        device_has_multiple_channels = hm_custom_entity.is_multi_channel_device(
            device_type=self._device.device_type, sub_type=self._device.sub_type
        )
        self.usage = self._custom_entity_usage()
        self.name = get_custom_entity_name(
            central=self._central,
            device_address=self.device_address,
            unique_id=self.unique_id,
            channel_no=channel_no,
            device_type=self.device_type,
            is_only_primary_channel=check_channel_is_only_primary_channel(
                current_channel=channel_no,
                device_def=device_def,
                device_has_multiple_channels=device_has_multiple_channels,
            ),
            usage=self.usage,
        )
        self.data_entities: dict[str, GenericEntity] = {}
        self._init_entities()

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the custom entity."""
        state_attr = super().attributes
        state_attr[ATTR_ENTITY_TYPE] = HmEntityType.CUSTOM.value
        return state_attr

    def _custom_entity_usage(self) -> HmEntityUsage:
        """Return the custom entity usage."""
        if secondary_channels := self._device_desc.get(
            hm_entity_definition.ED_SECONDARY_CHANNELS
        ):
            if self.channel_no in secondary_channels:
                return HmEntityUsage.CE_SECONDARY
        return HmEntityUsage.CE_PRIMARY

    async def put_paramset(
        self, paramset: str, value: Any, rx_mode: str | None = None
    ) -> None:
        """Set paramsets manually."""
        await self._client.put_paramset(
            channel_address=self.channel_address,
            paramset=paramset,
            value=value,
            rx_mode=rx_mode,
        )

    def _init_entities(self) -> None:
        """init entity collection"""

        fields_rep = self._device_desc.get(
            hm_entity_definition.ED_REPEATABLE_FIELDS, {}
        )
        # Add repeating fields
        for (field_name, parameter) in fields_rep.items():
            entity = self._device.get_hm_entity(
                channel_address=self.channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity)

        # Add sensor entities
        self._add_entities(
            field_dict_name=hm_entity_definition.ED_SENSOR_CHANNELS,
            is_sensor=True,
        )
        # Add device fields
        self._add_entities(
            field_dict_name=hm_entity_definition.ED_FIELDS,
        )

        # add device entities
        self._mark_entity(field_desc=self._entity_def)
        # add default entities
        if hm_entity_definition.get_include_default_entities(
            device_enum=self._device_enum
        ):
            self._mark_entity(field_desc=hm_entity_definition.get_default_entities())

        # add extra entities for the device type
        self._mark_entity(
            field_desc=hm_entity_definition.get_additional_entities_by_device_type(
                self.device_type
            )
        )

    def _add_entities(self, field_dict_name: str, is_sensor: bool = False) -> None:
        """Add entities to custom entity."""
        fields = self._device_desc.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for (field_name, parameter) in channel.items():
                channel_address = f"{self.device_address}:{channel_no}"
                if entity := self._device.get_hm_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    if is_sensor:
                        entity.usage = HmEntityUsage.CE_SENSOR
                    self._add_entity(field_name=field_name, entity=entity)

    def _mark_entity(self, field_desc: dict[int, set[str]]) -> None:
        """Mark entities to be created in HA."""
        if not field_desc:
            return None
        for channel_no, parameters in field_desc.items():
            channel_address = f"{self.device_address}:{channel_no}"
            for parameter in parameters:
                entity = self._device.get_hm_entity(
                    channel_address=channel_address, parameter=parameter
                )
                if entity:
                    entity.usage = HmEntityUsage.ENTITY

    def _add_entity(self, field_name: str, entity: GenericEntity | None) -> None:
        """Add entity to collection and register callback"""
        if not entity:
            return None

        entity.register_update_callback(self.update_entity)
        self.data_entities[field_name] = entity

    def _remove_entity(self, field_name: str, entity: GenericEntity | None) -> None:
        """Remove entity from collection and un-register callback"""
        if not entity:
            return None
        entity.unregister_update_callback(self.update_entity)
        del self.data_entities[field_name]

    async def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD

        for entity in self.data_entities.values():
            if entity:
                await entity.load_data()

        self.update_entity()
        return DATA_LOAD_SUCCESS

    def _get_entity(
        self, field_name: str, entity_type: type[_EntityType]
    ) -> _EntityType:
        """get entity"""
        if entity := self.data_entities.get(field_name):
            return cast(entity_type, entity)  # type: ignore
        return cast(entity_type, NoneTypeEntity())  # type: ignore

    def _get_entity_value(
        self, field_name: str, default: Any | None = None
    ) -> Any | None:
        """get entity value"""
        entity = self.data_entities.get(field_name)
        if entity:
            return entity.value
        return default


class BaseEvent(BaseParameterEntity[bool]):
    """Base class for action events"""

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
        event_type: HmEventType,
    ):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.EVENT,
        )

        self.name: str = get_event_name(
            central=self._central,
            channel_address=self.channel_address,
            parameter=self.parameter,
            unique_id=self.unique_id,
            device_type=self.device_type,
        )
        self.event_type: HmEventType = event_type
        self.usage = HmEntityUsage.EVENT
        self.last_update: datetime = INIT_DATETIME
        self._value: Any | None = None

        # Subscribe for all action events of this device
        if (
            self.channel_address,
            self.parameter,
        ) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[
                (self.channel_address, self.parameter)
            ] = []
        self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ].append(self.event)

    def event(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Handle event for which this handler has subscribed.
        """
        _LOGGER.debug(
            "Entity.event: %s, %s, %s, %s",
            interface_id,
            channel_address,
            parameter,
            value,
        )
        if interface_id != self._interface_id:
            _LOGGER.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
            )
            return
        if channel_address != self.channel_address:
            _LOGGER.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                channel_address,
                self.channel_address,
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
    def value(self) -> Any:
        """Return the value."""
        return self._value

    async def send_value(self, value: Any) -> None:
        """Send value to ccu."""
        try:
            await self._client.set_value(
                channel_address=self.channel_address,
                parameter=self.parameter,
                value=value,
            )
        except Exception:
            _LOGGER.exception(
                "action_event: Failed to send value for: %s, %s, %s",
                self.channel_address,
                self.parameter,
                value,
            )

    def add_to_collections(self) -> None:
        """Add entity to central_unit collections."""
        self._device.add_hm_action_event(self)

    def _set_last_update(self) -> None:
        self.last_update = datetime.now()

    @abstractmethod
    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""

    @abstractmethod
    def fire_event(self, value: Any) -> None:
        """
        Do what is needed to fire an event.
        """

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ]


class ClickEvent(BaseEvent):
    """
    class for handling click events.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            event_type=HmEventType.KEYPRESS,
        )

    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: self.device_address,
            ATTR_TYPE: self.parameter.lower(),
            ATTR_SUBTYPE: self.channel_no,
        }

    def fire_event(self, value: Any) -> None:
        """
        Do what is needed to fire an event.
        """
        if callable(self._central.callback_ha_event):
            self._central.callback_ha_event(
                self.event_type,
                self.get_event_data(),
            )


class SpecialEvent(BaseEvent):
    """
    class for handling special events.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            event_type=HmEventType.SPECIAL,
        )

    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: self.device_address,
            ATTR_PARAMETER: self.parameter,
            ATTR_VALUE: value,
        }

    def fire_event(self, value: bool | None) -> None:
        """
        Do what is needed to fire an event.
        """
        if self._value == value:
            return None
        old_value = self._value
        self._set_last_update()
        self._value = value

        if self.parameter == EVENT_CONFIG_PENDING:
            if value is False and old_value is True:
                self._central.create_task(self._device.reload_paramsets())
            return None

        if self.parameter in (EVENT_UN_REACH, EVENT_STICKY_UN_REACH):
            self._device.update_device(self.unique_id)
            # no return here. Event should also be fired for persistent notification.

        if callable(self._central.callback_ha_event):
            self._central.callback_ha_event(
                self.event_type,
                self.get_event_data(value),
            )


def fix_unit(unit: str | None) -> str | None:
    """replace given unit"""
    if not unit:
        return None
    for (check, fix) in HM_ENTITY_UNIT_REPLACE.items():
        if check in unit:
            return fix
    return unit


class NoneTypeEntity:
    """Entity to return an empty value."""

    default: Any = None
    hmtype: Any = None
    max: Any = None
    min: Any = None
    unit: Any = None
    value: Any = None
    value_list: list[Any] = []
    visible: Any = None

    def send_value(self, value: Any) -> None:
        """Dummy method."""
