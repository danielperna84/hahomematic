"""
Functions for entity creation.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, Final, Generic, TypeVar, Union, cast

from slugify import slugify

import hahomematic.central_unit as hm_central
import hahomematic.client as hm_client
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_DEVICE_TYPE,
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
    CHANNEL_OPERATION_MODE_VISIBILITY,
    CONFIGURABLE_CHANNEL,
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    FLAG_SERVICE,
    FLAG_VISIBLE,
    HM_ENTITY_UNIT_REPLACE,
    INIT_DATETIME,
    NO_CACHE_ENTRY,
    OPERATION_EVENT,
    OPERATION_READ,
    OPERATION_WRITE,
    PARAM_CHANNEL_OPERATION_MODE,
    PARAMSET_KEY_VALUES,
    SYSVAR_ADDRESS,
    TYPE_BOOL,
    HmCallSource,
    HmEntityUsage,
    HmEventType,
    HmPlatform,
)
import hahomematic.device as hm_device
import hahomematic.devices as hm_custom_entity
import hahomematic.devices.entity_definition as hm_entity_definition
from hahomematic.exceptions import BaseHomematicException
from hahomematic.helpers import (
    EntityNameData,
    HubData,
    SystemVariableData,
    check_channel_is_only_primary_channel,
    convert_value,
    generate_unique_identifier,
    get_custom_entity_name,
    get_device_channel,
    get_entity_name,
    get_event_name,
    parse_sys_var,
    updated_within_seconds,
)
from hahomematic.parameter_visibility import HIDDEN_PARAMETERS

_LOGGER = logging.getLogger(__name__)
# pylint: disable=consider-alternative-union-syntax
ParameterT = TypeVar("ParameterT", bool, int, float, str, Union[int, str], None)


class CallbackEntity(ABC):
    """Base class for callback entities."""

    def __init__(self) -> None:
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

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """register the remove callback"""
        if callable(remove_callback) and remove_callback not in self._remove_callbacks:
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """remove the remove callback"""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def update_entity(self, *args: Any) -> None:
        """
        Do what is needed when the value of the entity has been updated.
        """
        for _callback in self._update_callbacks:
            _callback(*args)

    def remove_entity(self, *args: Any) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        for _callback in self._remove_callbacks:
            _callback(*args)


class BaseEntity(ABC):
    """Base class for regular entities."""

    _attr_platform: HmPlatform

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_identifier: str,
        channel_no: int,
    ):
        """
        Initialize the entity.
        """
        self.device: Final[hm_device.HmDevice] = device
        self.unique_identifier: Final[str] = unique_identifier
        self.channel_no: Final[int] = channel_no
        self.channel_address: Final[str] = f"{device.device_address}:{channel_no}"
        self._central: Final[hm_central.CentralUnit] = device.central
        self._channel_type: Final[str] = str(device.channels[self.channel_address].type)
        self.function: Final[
            str | None
        ] = self._central.device_details.get_function_text(address=self.channel_address)
        self._usage: HmEntityUsage = self._generate_entity_usage()
        self._client: Final[hm_client.Client] = device.central.clients[
            device.interface_id
        ]
        self.entity_name_data: Final[EntityNameData] = self._generate_entity_name_data()
        self.name: Final[str | None] = self.entity_name_data.entity_name

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.device.available

    @property
    def force_enabled(self) -> bool | None:
        """Return, if the entity/event must be enabled."""
        return None

    @property
    def platform(self) -> HmPlatform:
        """Return, the platform of the entity."""
        return self._attr_platform

    @property
    def usage(self) -> HmEntityUsage:
        """Return the entity usage."""
        if self.force_enabled is None:
            return self._usage
        if isinstance(self, GenericEntity) and self.force_enabled is True:
            return HmEntityUsage.ENTITY
        if isinstance(self, BaseEvent) and self.force_enabled is True:
            return HmEntityUsage.EVENT
        return HmEntityUsage.ENTITY_NO_CREATE

    @usage.setter
    def usage(self, usage: HmEntityUsage) -> None:
        """Set the entity usage."""
        self._usage = usage

    def add_to_collections(self) -> None:
        """add entity to central_unit collections"""
        self.device.add_hm_entity(self)
        self._central.hm_entities[self.unique_identifier] = self

    async def load_entity_value(self, call_source: HmCallSource) -> None:
        """Init the entity data."""
        return None

    @abstractmethod
    def _generate_entity_name_data(self) -> EntityNameData:
        """Generate the name for the entity."""

    def _generate_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        return (
            HmEntityUsage.ENTITY_NO_CREATE
            if self.device.is_custom_entity
            else HmEntityUsage.ENTITY
        )

    def __str__(self) -> str:
        """
        Provide some useful information.
        """
        return f"address: {self.channel_address}, type: {self.device.device_type}, name: {self.entity_name_data.full_name}"


class BaseParameterEntity(Generic[ParameterT], BaseEntity):
    """
    Base class for stateless entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_identifier: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        """
        Initialize the entity.
        """
        self.paramset_key: Final[str] = paramset_key
        # required for name in BaseEntity
        self.parameter: Final[str] = parameter
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_no=get_device_channel(channel_address),
        )
        self._assign_parameter_data(parameter_data=parameter_data)

    def _assign_parameter_data(self, parameter_data: dict[str, Any]) -> None:
        """Assign parameter data to instance variables."""
        self._type: str = parameter_data[ATTR_HM_TYPE]
        self._value_list: list[str] | None = parameter_data.get(ATTR_HM_VALUE_LIST)
        self._max: ParameterT = self._convert_value(parameter_data[ATTR_HM_MAX])
        self._min: ParameterT = self._convert_value(parameter_data[ATTR_HM_MIN])
        self._default: ParameterT = self._convert_value(
            parameter_data.get(ATTR_HM_DEFAULT, self._min)
        )
        flags: int = parameter_data[ATTR_HM_FLAGS]
        self._visible: bool = flags & FLAG_VISIBLE == FLAG_VISIBLE
        self._service: bool = flags & FLAG_SERVICE == FLAG_SERVICE
        self._operations: int = parameter_data[ATTR_HM_OPERATIONS]
        self._special: dict[str, Any] | None = parameter_data.get(ATTR_HM_SPECIAL)
        self._unit: str | None = parameter_data.get(ATTR_HM_UNIT)

    @property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._default

    @property
    def hmtype(self) -> str:
        """Return the homematic type."""
        return self._type

    @property
    def max(self) -> ParameterT:
        """Return max value."""
        return self._max

    @property
    def min(self) -> ParameterT:
        """Return min value."""
        return self._min

    @property
    def multiplier(self) -> int:
        """Return multiplier value."""
        return 100 if self._unit and self._unit == "100%" else 1

    @property
    def operations(self) -> int:
        """Return the operations mode of the entity."""
        return self._operations

    @property
    def is_readable(self) -> bool:
        """Return, if entity is readable."""
        return bool(self._operations & OPERATION_READ)

    @property
    def is_writeable(self) -> bool:
        """Return, if entity is writeable."""
        return bool(self._operations & OPERATION_WRITE)

    @property
    def supports_events(self) -> bool:
        """Return, if entity is supports events."""
        return bool(self._operations & OPERATION_EVENT)

    @property
    def unit(self) -> str | None:
        """Return unit value."""
        return fix_unit(self._unit)

    @property
    def value_list(self) -> list[str] | None:
        """Return the value_list."""
        return self._value_list

    @property
    def visible(self) -> bool:
        """Return the if entity is visible in ccu."""
        return self._visible

    def update_parameter_data(self) -> None:
        """Update parameter data"""
        self._assign_parameter_data(
            parameter_data=self.device.central.paramset_descriptions.get_parameter_data(
                interface_id=self.device.interface_id,
                channel_address=self.channel_address,
                paramset_key=self.paramset_key,
                parameter=self.parameter,
            )
        )

    def _check_event_parameters(
        self,
        interface_id: str,
        channel_address: str,
        parameter: str,
    ) -> bool:
        """Check the parameters of an event."""
        _LOGGER.debug(
            "event: %s, %s, %s",
            interface_id,
            channel_address,
            parameter,
        )
        if interface_id != self.device.interface_id:
            _LOGGER.warning(
                "event failed: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self.device.interface_id,
            )
            return False
        if channel_address != self.channel_address:
            _LOGGER.warning(
                "event failed: Incorrect address: %s - should be: %s",
                channel_address,
                self.channel_address,
            )
            return False
        if parameter != self.parameter:
            _LOGGER.warning(
                "event failed: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return False
        return True

    def _convert_value(self, value: ParameterT) -> ParameterT:
        """Convert to value to ParameterT"""
        if value is None:
            return None
        try:
            if (
                self._type == TYPE_BOOL
                and self._value_list is not None
                and value is not None
                and isinstance(value, str)
            ):
                return convert_value(  # type: ignore[no-any-return]
                    value=self._value_list.index(value), target_type=self._type
                )
            return convert_value(value=value, target_type=self._type)  # type: ignore[no-any-return]
        except ValueError:
            _LOGGER.debug(
                "_convert_value: conversion failed for %s, %s, %s, value: [%s]",
                self.device.interface_id,
                self.channel_address,
                self.parameter,
                value,
            )
            return None  # type: ignore[return-value]

    def _generate_entity_name_data(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_entity_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            parameter=self.parameter,
        )

    def _generate_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        usage = super()._generate_entity_usage()
        if self.parameter in HIDDEN_PARAMETERS:
            usage = HmEntityUsage.ENTITY_NO_CREATE
        return usage


class GenericEntity(BaseParameterEntity[ParameterT], CallbackEntity):
    """
    Base class for generic entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_identifier: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        """
        Initialize the entity.
        """
        BaseParameterEntity.__init__(
            self=self,
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        CallbackEntity.__init__(self)
        self._value: ParameterT | None = None
        self._last_update: datetime = INIT_DATETIME
        self._state_uncertain: bool = True

        # Subscribe for all events of this device
        if (channel_address, parameter) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []
        self._central.entity_event_subscriptions[(channel_address, parameter)].append(
            self.event
        )

    @property
    def channel_operation_mode(self) -> str | None:
        """Return the channel operation mode if available."""
        cop: GenericEntity | None = self.device.entities.get(
            (self.channel_address, PARAM_CHANNEL_OPERATION_MODE)
        )
        if cop and cop.value:
            return str(cop.value)
        return None

    @property
    def force_enabled(self) -> bool | None:
        """Return, if the entity/event must be enabled."""
        if self.channel_operation_mode is None:
            return None
        if (
            self._channel_type in CONFIGURABLE_CHANNEL
            and self.parameter in CHANNEL_OPERATION_MODE_VISIBILITY
            and self.channel_operation_mode
            in CHANNEL_OPERATION_MODE_VISIBILITY[self.parameter]
        ):
            return True
        return False

    @property
    def is_valid(self) -> bool:
        """Return, if the value of the entity is valid based on the last updated datetime."""
        return self._last_update > INIT_DATETIME

    @property
    def last_update(self) -> datetime:
        """Return the last updated datetime value"""
        return self._last_update

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._state_uncertain

    @property
    def value(self) -> ParameterT | None:
        """Return the value of the entity."""
        return self._value

    def event(
        self, interface_id: str, channel_address: str, parameter: str, raw_value: Any
    ) -> None:
        """
        Handle event for which this entity has subscribed.
        """
        old_value = self._value

        value = self._convert_value(raw_value)
        if self._value == value:
            return

        if not self._check_event_parameters(
            interface_id=interface_id,
            channel_address=channel_address,
            parameter=parameter,
        ):
            return

        self.update_value(value=value)

        # send device events, if value has changed
        if self.parameter in (
            EVENT_CONFIG_PENDING,
            EVENT_UN_REACH,
            EVENT_STICKY_UN_REACH,
        ):
            if self.parameter in (EVENT_UN_REACH, EVENT_STICKY_UN_REACH):
                self.device.update_device(self.unique_identifier)

            if self.parameter == EVENT_CONFIG_PENDING:
                if value is False and old_value is True:
                    self._central.create_task(
                        self.device.reload_paramset_descriptions()
                    )
                return None

            if callable(self._central.callback_ha_event):
                self._central.callback_ha_event(
                    HmEventType.DEVICE,
                    self._get_event_data(value),
                )

    async def load_entity_value(
        self,
        call_source: HmCallSource,
    ) -> None:
        """Init the entity data."""
        if updated_within_seconds(last_update=self._last_update):
            return None

        # Check, if entity is readable
        if not self.is_readable:
            return None

        self.update_value(
            value=await self.device.value_cache.get_value(
                channel_address=self.channel_address,
                paramset_key=self.paramset_key,
                parameter=self.parameter,
                call_source=call_source,
            )
        )

    def update_value(self, value: Any) -> None:
        """Update value of the entity."""
        if value == NO_CACHE_ENTRY:
            if self.last_update != INIT_DATETIME:
                self._state_uncertain = True
                self.update_entity()
            return
        self._value = self._convert_value(value)
        self._state_uncertain = False
        self._set_last_update()
        self.update_entity()

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ]

    async def send_value(self, value: Any) -> None:
        """send value to ccu."""
        await self._client.set_value(
            channel_address=self.channel_address,
            paramset_key=self.paramset_key,
            parameter=self.parameter,
            value=self._convert_value(value),
        )

    def _get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""
        return {
            ATTR_INTERFACE_ID: self.device.interface_id,
            ATTR_ADDRESS: self.device.device_address,
            ATTR_DEVICE_TYPE: self.device.device_type,
            ATTR_PARAMETER: self.parameter,
            ATTR_VALUE: value,
        }

    def _set_last_update(self) -> None:
        """Set last_update to current datetime."""
        self._last_update = datetime.now()


_EntityT = TypeVar("_EntityT", bound=GenericEntity)


class CustomEntity(BaseEntity, CallbackEntity):
    """
    Base class for custom entities.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_identifier: str,
        device_enum: hm_entity_definition.EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int, set[str]],
        channel_no: int,
    ):
        """
        Initialize the entity.
        """
        self._device_enum: Final[hm_entity_definition.EntityDefinition] = device_enum
        # required for name in BaseEntity
        self._device_desc: Final[dict[str, Any]] = device_def
        self._entity_def: Final[dict[int, set[str]]] = entity_def
        BaseEntity.__init__(
            self=self,
            device=device,
            unique_identifier=unique_identifier,
            channel_no=channel_no,
        )
        CallbackEntity.__init__(self)
        self.data_entities: dict[str, GenericEntity] = {}
        self._init_entities()
        self._init_entity_fields()

    @abstractmethod
    def _init_entity_fields(self) -> None:
        """Init the entity fields."""

    @property
    def last_update(self) -> datetime:
        """Return the latest last_update timestamp."""
        latest_update: datetime = INIT_DATETIME
        for hm_entity in self._readable_entities:
            if entity_last_update := hm_entity.last_update:
                if entity_last_update > latest_update:
                    latest_update = entity_last_update
        return latest_update

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        for hm_entity in self._readable_entities:
            if hm_entity.is_valid is False:
                return False
        return True

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        for hm_entity in self._readable_entities:
            if hm_entity.state_uncertain:
                return True
        return False

    @property
    def _readable_entities(self) -> list[GenericEntity]:
        """Returns the list of readable entities."""
        return [e for e in self.data_entities.values() if e.is_readable]

    def _generate_entity_name_data(self) -> EntityNameData:
        """Create the name for the entity."""
        device_has_multiple_channels = hm_custom_entity.is_multi_channel_device(
            device_type=self.device.device_type, sub_type=self.device.sub_type
        )
        is_only_primary_channel = check_channel_is_only_primary_channel(
            current_channel=self.channel_no,
            device_def=self._device_desc,
            device_has_multiple_channels=device_has_multiple_channels,
        )
        return get_custom_entity_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            is_only_primary_channel=is_only_primary_channel,
            usage=self._usage,
        )

    def _generate_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        if secondary_channels := self._device_desc.get(
            hm_entity_definition.ED_SECONDARY_CHANNELS
        ):
            if self.channel_no in secondary_channels:
                return HmEntityUsage.CE_SECONDARY
        return HmEntityUsage.CE_PRIMARY

    async def put_paramset(
        self, paramset_key: str, value: Any, rx_mode: str | None = None
    ) -> None:
        """Set paramsets manually."""
        await self._client.put_paramset(
            address=self.channel_address,
            paramset_key=paramset_key,
            value=value,
            rx_mode=rx_mode,
        )

    async def load_entity_value(self, call_source: HmCallSource) -> None:
        """Init the entity values."""
        for entity in self.data_entities.values():
            if entity:
                await entity.load_entity_value(call_source=call_source)
        self.update_entity()

    def _init_entities(self) -> None:
        """init entity collection"""

        repeating_fields = self._device_desc.get(
            hm_entity_definition.ED_REPEATABLE_FIELDS, {}
        )
        # Add repeating fields
        for (field_name, parameter) in repeating_fields.items():
            entity = self.device.get_hm_entity(
                channel_address=self.channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity)

        visible_repeating_fields = self._device_desc.get(
            hm_entity_definition.ED_VISIBLE_REPEATABLE_FIELDS, {}
        )
        # Add visible repeating fields
        for (field_name, parameter) in visible_repeating_fields.items():
            entity = self.device.get_hm_entity(
                channel_address=self.channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity, is_visible=True)

        # Add device fields
        self._add_entities(
            field_dict_name=hm_entity_definition.ED_FIELDS,
        )
        # Add visible device fields
        self._add_entities(
            field_dict_name=hm_entity_definition.ED_VISIBLE_FIELDS,
            is_visible=True,
        )

        # Add default device entities
        self._mark_entity(field_desc=self._entity_def)
        # add default entities
        if hm_entity_definition.get_include_default_entities(
            device_enum=self._device_enum
        ):
            self._mark_entity(field_desc=hm_entity_definition.get_default_entities())

        # add extra entities for the device type
        self._mark_entity(
            field_desc=hm_entity_definition.get_additional_entities_by_device_type(
                self.device.device_type
            )
        )

        # add custom un_ignore entities
        self._mark_entity_by_custom_un_ignore_parameters(
            un_ignore_params_by_paramset_key=self._central.parameter_visibility.get_un_ignore_parameters(
                device_type=self.device.device_type, device_channel=self.channel_no
            )
        )

    def _add_entities(self, field_dict_name: str, is_visible: bool = False) -> None:
        """Add entities to custom entity."""
        fields = self._device_desc.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for (field_name, parameter) in channel.items():
                channel_address = f"{self.device.device_address}:{channel_no}"
                if entity := self.device.get_hm_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    if is_visible:
                        entity.usage = HmEntityUsage.CE_VISIBLE
                    self._add_entity(field_name=field_name, entity=entity)

    def _mark_entity(self, field_desc: dict[int, set[str]]) -> None:
        """Mark entities to be created in HA."""
        if not field_desc:
            return None
        for channel_no, parameters in field_desc.items():
            channel_address = f"{self.device.device_address}:{channel_no}"
            for parameter in parameters:
                entity = self.device.get_hm_entity(
                    channel_address=channel_address, parameter=parameter
                )
                if entity:
                    entity.usage = HmEntityUsage.ENTITY

    def _mark_entity_by_custom_un_ignore_parameters(
        self, un_ignore_params_by_paramset_key: dict[str, set[str]]
    ) -> None:
        """Mark entities to be created in HA."""
        if not un_ignore_params_by_paramset_key:
            return None
        for paramset_key, un_ignore_params in un_ignore_params_by_paramset_key.items():
            for entity in self.device.entities.values():
                if (
                    entity.paramset_key == paramset_key
                    and entity.parameter in un_ignore_params
                ):
                    entity.usage = HmEntityUsage.ENTITY

    def _add_entity(
        self, field_name: str, entity: GenericEntity | None, is_visible: bool = False
    ) -> None:
        """Add entity to collection and register callback"""
        if not entity:
            return None

        if is_visible:
            entity.usage = HmEntityUsage.CE_VISIBLE

        entity.register_update_callback(self.update_entity)
        self.data_entities[field_name] = entity

    def _remove_entity(self, field_name: str, entity: GenericEntity | None) -> None:
        """Remove entity from collection and un-register callback"""
        if not entity:
            return None
        entity.unregister_update_callback(self.update_entity)
        del self.data_entities[field_name]

    def _get_entity(self, field_name: str, entity_type: type[_EntityT]) -> _EntityT:
        """get entity"""
        if entity := self.data_entities.get(field_name):
            return cast(entity_type, entity)  # type: ignore
        return cast(entity_type, NoneTypeEntity())  # type: ignore


class GenericHubEntity(CallbackEntity):
    """Class for a homematic system variable."""

    _attr_platform: HmPlatform

    def __init__(
        self,
        central: hm_central.CentralUnit,
        address: str,
        data: HubData,
    ):
        """
        Initialize the entity.
        """
        CallbackEntity.__init__(self)
        self.central: Final[hm_central.CentralUnit] = central
        self.unique_identifier: Final[str] = generate_unique_identifier(
            central=central,
            address=address,
            parameter=slugify(data.name),
        )
        self.name: Final[str] = self.get_name(data=data)
        self.create_in_ha: bool = True
        self.usage: Final[HmEntityUsage] = HmEntityUsage.ENTITY

    @property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @abstractmethod
    def get_name(self, data: HubData) -> str:
        """Return the name of the hub entity."""

    @property
    def platform(self) -> HmPlatform:
        """Return, the platform of the entity."""
        return self._attr_platform


class GenericSystemVariable(GenericHubEntity):
    """Class for a homematic system variable."""

    _attr_is_extended = False

    def __init__(
        self,
        central: hm_central.CentralUnit,
        data: SystemVariableData,
    ):
        """
        Initialize the entity.
        """
        super().__init__(central=central, address=SYSVAR_ADDRESS, data=data)
        self.ccu_var_name: Final[str] = data.name
        self.data_type: Final[str | None] = data.data_type
        self.value_list: Final[list[str] | None] = data.value_list
        self.max: Final[float | int | None] = data.max_value
        self.min: Final[float | int | None] = data.min_value
        self._unit: Final[str | None] = data.unit
        self._value: bool | float | int | str | None = data.value

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @property
    def value(self) -> Any | None:
        """Return the value."""
        return self._value

    @property
    def unit(self) -> str | None:
        """Return the unit of the entity."""
        if self._unit:
            return self._unit
        if isinstance(self._value, (int, float)):
            return " "
        return None

    @property
    def is_extended(self) -> bool:
        """Return if the entity is an extended type."""
        return self._attr_is_extended

    def get_name(self, data: HubData) -> str:
        """Return the name of the sysvar entity."""
        return f"SV_{data.name}"

    def update_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if self.data_type:
            value = parse_sys_var(data_type=self.data_type, raw_value=value)
        else:
            old_value = self._value
            if isinstance(old_value, bool):
                value = bool(value)
            elif isinstance(old_value, int):
                value = int(value)
            elif isinstance(old_value, str):
                value = str(value)
            elif isinstance(old_value, float):
                value = float(value)

        if self._value != value:
            self._value = value
            self.update_entity()

    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        await self.central.set_system_variable(
            name=self.ccu_var_name, value=parse_sys_var(self.data_type, value)
        )
        self.update_value(value=value)


class BaseEvent(BaseParameterEntity[bool]):
    """Base class for action events"""

    _attr_platform = HmPlatform.EVENT
    _attr_event_type: HmEventType

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_identifier: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            paramset_key=PARAMSET_KEY_VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
        )

        self._last_update: datetime = INIT_DATETIME
        self._value: Any | None = None

        # Subscribe for all action events of this device
        if (
            channel_address,
            parameter,
        ) not in self._central.entity_event_subscriptions:
            self._central.entity_event_subscriptions[(channel_address, parameter)] = []
        self._central.entity_event_subscriptions[(channel_address, parameter)].append(
            self.event
        )

    @property
    def event_type(self) -> HmEventType:
        """Return the event_type of the event."""
        return self._attr_event_type

    def event(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Handle event for which this handler has subscribed.
        """
        if not self._check_event_parameters(
            interface_id=interface_id,
            channel_address=channel_address,
            parameter=parameter,
        ):
            return

        # fire an event
        self.fire_event(value)

    @property
    def value(self) -> Any:
        """Return the value."""
        return self._value

    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data."""
        event_data = {
            ATTR_INTERFACE_ID: self.device.interface_id,
            ATTR_ADDRESS: self.device.device_address,
            ATTR_TYPE: self.parameter.lower(),
            ATTR_SUBTYPE: self.channel_no,
        }

        if value is not None:
            event_data[ATTR_VALUE] = value

        return event_data

    def fire_event(self, value: Any) -> None:
        """
        Do what is needed to fire an event.
        """
        if callable(self._central.callback_ha_event):
            self._central.callback_ha_event(
                self.event_type,
                self.get_event_data(value=value),
            )

    def _generate_entity_name_data(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_event_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            parameter=self.parameter,
        )

    def _generate_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        return HmEntityUsage.EVENT

    async def send_value(self, value: Any) -> None:
        """Send value to ccu."""
        try:
            await self._client.set_value(
                channel_address=self.channel_address,
                paramset_key=self.paramset_key,
                parameter=self.parameter,
                value=value,
            )
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "action_event failed: %s [%s] Unable to send value for: %s, %s, %s",
                hhe.name,
                hhe.args,
                self.channel_address,
                self.parameter,
                value,
            )

    def add_to_collections(self) -> None:
        """Add entity to central_unit collections."""
        self.device.add_hm_action_event(self)

    def _set_last_update(self) -> None:
        self._last_update = datetime.now()

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._central.entity_event_subscriptions[
            (self.channel_address, self.parameter)
        ]


class ClickEvent(BaseEvent):
    """
    class for handling click events.
    """

    _attr_event_type = HmEventType.KEYPRESS


class ImpulseEvent(BaseEvent):
    """
    class for handling impulse events.
    """

    _attr_event_type = HmEventType.IMPULSE


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
    is_valid: bool = False
    max: Any = None
    min: Any = None
    unit: Any = None
    value: Any = None
    value_list: list[Any] = []
    visible: Any = None
    channel_operation_mode: str | None = None

    def send_value(self, value: Any) -> None:
        """Dummy method."""
