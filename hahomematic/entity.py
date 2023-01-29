"""Functions for entity creation."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any, Final, Generic, TypeVar, cast

from slugify import slugify
import voluptuous as vol

import hahomematic.central_unit as hmcu
import hahomematic.client as hmcl
from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_CHANNEL_NO,
    ATTR_DEVICE_TYPE,
    ATTR_INTERFACE_ID,
    ATTR_PARAMETER,
    ATTR_VALUE,
    CHANNEL_OPERATION_MODE_VISIBILITY,
    CONFIGURABLE_CHANNEL,
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    FIX_UNIT_BY_PARAM,
    FIX_UNIT_REPLACE,
    FLAG_SERVICE,
    FLAG_VISIBLE,
    HM_DEFAULT,
    HM_FLAGS,
    HM_MAX,
    HM_MIN,
    HM_OPERATIONS,
    HM_SPECIAL,
    HM_TYPE,
    HM_UNIT,
    HM_VALUE_LIST,
    INIT_DATETIME,
    MAX_CACHE_AGE,
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
import hahomematic.custom_platforms as hmce
import hahomematic.custom_platforms.entity_definition as hmed
from hahomematic.decorators import config_property, value_property
import hahomematic.device as hmd
from hahomematic.exceptions import HaHomematicException
from hahomematic.helpers import (
    EntityNameData,
    HubData,
    SystemVariableData,
    check_channel_is_the_only_primary_channel,
    convert_value,
    generate_unique_identifier,
    get_custom_entity_name,
    get_device_channel,
    get_entity_name,
    get_event_name,
    parse_sys_var,
    updated_within_seconds,
)

HM_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ADDRESS): str,
        vol.Required(ATTR_CHANNEL_NO): int,
        vol.Required(ATTR_DEVICE_TYPE): str,
        vol.Required(ATTR_INTERFACE_ID): str,
        vol.Required(ATTR_PARAMETER): str,
        vol.Optional(ATTR_VALUE): vol.Any(bool, int),
    }
)

ParameterT = TypeVar("ParameterT", bool, int, float, str, int | str, None)
_LOGGER = logging.getLogger(__name__)


class CallbackEntity(ABC):
    """Base class for callback entities."""

    _attr_platform: HmPlatform

    def __init__(self, unique_identifier: str) -> None:
        """Init the callback entity."""
        self._attr_unique_identifier: Final[str] = unique_identifier
        self._update_callbacks: list[Callable] = []
        self._remove_callbacks: list[Callable] = []

    @value_property
    @abstractmethod
    def available(self) -> bool:
        """Return the availability of the device."""

    @config_property
    @abstractmethod
    def full_name(self) -> str:
        """Return the full name of the entity."""

    @config_property
    @abstractmethod
    def name(self) -> str | None:
        """Return the name of the entity."""

    @config_property
    def platform(self) -> HmPlatform:
        """Return, the platform of the entity."""
        return self._attr_platform

    @config_property
    def unique_identifier(self) -> str:
        """Return the unique_identifier."""
        return self._attr_unique_identifier

    @config_property
    def usage(self) -> HmEntityUsage:
        """Return the entity usage."""
        return HmEntityUsage.ENTITY

    @config_property
    def enabled_default(self) -> bool:
        """Return, if entity should be enabled based on usage attribute."""
        return self.usage in (
            HmEntityUsage.CE_PRIMARY,
            HmEntityUsage.ENTITY,
            HmEntityUsage.EVENT,
        )

    def register_update_callback(self, update_callback: Callable) -> None:
        """register update callback."""
        if callable(update_callback):
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """remove update callback."""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """register the remove callback."""
        if callable(remove_callback) and remove_callback not in self._remove_callbacks:
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """remove the remove callback."""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def update_entity(self, *args: Any) -> None:
        """Do what is needed when the value of the entity has been updated."""
        for _callback in self._update_callbacks:
            _callback(*args)

    def remove_entity(self, *args: Any) -> None:
        """Do what is needed when the entity has been removed."""
        for _callback in self._remove_callbacks:
            _callback(*args)


class BaseEntity(CallbackEntity):
    """Base class for regular entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_no: int,
    ) -> None:
        """Initialize the entity."""
        super().__init__(unique_identifier=unique_identifier)
        self.device: Final[hmd.HmDevice] = device
        self._attr_channel_no: Final[int] = channel_no
        self._attr_channel_address: Final[str] = f"{device.device_address}:{channel_no}"
        self._central: Final[hmcu.CentralUnit] = device.central
        self._channel_type: Final[str] = str(device.channels[self._attr_channel_address].type)
        self._attr_function: Final[str | None] = self._central.device_details.get_function_text(
            address=self._attr_channel_address
        )
        self._client: Final[hmcl.Client] = device.central.get_client(
            interface_id=device.interface_id
        )

        self._attr_usage: HmEntityUsage = self._get_entity_usage()
        entity_name_data: Final[EntityNameData] = self._get_entity_name()
        self._attr_full_name: Final[str] = entity_name_data.full_name
        self._attr_name: Final[str | None] = entity_name_data.entity_name

    @value_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.device.available

    @property
    def _force_enabled(self) -> bool | None:
        """Return, if the entity/event must be enabled."""
        return None

    @config_property
    def channel_address(self) -> str:
        """Return the channel_address of the entity."""
        return self._attr_channel_address

    @config_property
    def channel_no(self) -> int:
        """Return the channel_no of the entity."""
        return self._attr_channel_no

    @config_property
    def function(self) -> str | None:
        """Return the function of the entity."""
        return self._attr_function

    @config_property
    def full_name(self) -> str:
        """Return the full name of the entity."""
        return self._attr_full_name

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._attr_name

    @config_property
    def usage(self) -> HmEntityUsage:
        """Return the entity usage."""
        if self._force_enabled is None:
            return self._attr_usage
        if isinstance(self, GenericEntity) and self._force_enabled is True:
            return HmEntityUsage.ENTITY
        if isinstance(self, GenericEvent) and self._force_enabled is True:
            return HmEntityUsage.EVENT
        return HmEntityUsage.ENTITY_NO_CREATE

    def set_usage(self, usage: HmEntityUsage) -> None:
        """Set the entity usage."""
        self._attr_usage = usage

    @abstractmethod
    async def load_entity_value(
        self, call_source: HmCallSource, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Init the entity data."""

    @abstractmethod
    def _get_entity_name(self) -> EntityNameData:
        """Generate the name for the entity."""

    @abstractmethod
    def _get_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""

    def __str__(self) -> str:
        """Provide some useful information."""
        return (
            f"address: {self._attr_channel_address}, type: {self.device.device_type}, "
            f"name: {self.full_name}"
        )


class BaseParameterEntity(Generic[ParameterT], BaseEntity):
    """Base class for stateless entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ) -> None:
        """Initialize the entity."""
        self._attr_paramset_key: Final[str] = paramset_key
        # required for name in BaseEntity
        self._attr_parameter: Final[str] = parameter
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_no=get_device_channel(channel_address),
        )
        self._attr_value: ParameterT | None = None
        self._attr_last_update: datetime = INIT_DATETIME
        self._attr_state_uncertain: bool = True
        self._assign_parameter_data(parameter_data=parameter_data)

    def _assign_parameter_data(self, parameter_data: dict[str, Any]) -> None:
        """Assign parameter data to instance variables."""
        self._attr_type: str = parameter_data[HM_TYPE]
        self._attr_value_list: tuple[str, ...] | None = None
        if HM_VALUE_LIST in parameter_data:
            self._attr_value_list = tuple(parameter_data[HM_VALUE_LIST])
        self._attr_max: ParameterT = self._convert_value(parameter_data[HM_MAX])
        self._attr_min: ParameterT = self._convert_value(parameter_data[HM_MIN])
        self._attr_default: ParameterT = self._convert_value(
            parameter_data.get(HM_DEFAULT, self._attr_min)
        )
        flags: int = parameter_data[HM_FLAGS]
        self._attr_visible: bool = flags & FLAG_VISIBLE == FLAG_VISIBLE
        self._attr_service: bool = flags & FLAG_SERVICE == FLAG_SERVICE
        self._attr_operations: int = parameter_data[HM_OPERATIONS]
        self._attr_special: dict[str, Any] | None = parameter_data.get(HM_SPECIAL)
        self._attr_raw_unit: str | None = parameter_data.get(HM_UNIT)
        self._attr_unit: str | None = self._fix_unit(raw_unit=self._attr_raw_unit)

    @config_property
    def default(self) -> ParameterT:
        """Return default value."""
        return self._attr_default

    @config_property
    def hmtype(self) -> str:
        """Return the HomeMatic type."""
        return self._attr_type

    @config_property
    def is_unit_fixed(self) -> bool:
        """Return if the unit is fixed."""
        return self._attr_raw_unit != self._attr_unit

    @config_property
    def max(self) -> ParameterT:
        """Return max value."""
        return self._attr_max

    @config_property
    def min(self) -> ParameterT:
        """Return min value."""
        return self._attr_min

    @config_property
    def multiplier(self) -> int:
        """Return multiplier value."""
        return 100 if self._attr_raw_unit and self._attr_raw_unit == "100%" else 1

    @config_property
    def parameter(self) -> str:
        """Return parameter name."""
        return self._attr_parameter

    @config_property
    def paramset_key(self) -> str:
        """Return paramset_key name."""
        return self._attr_paramset_key

    @config_property
    def raw_unit(self) -> str | None:
        """Return raw unit value."""
        return self._attr_raw_unit

    @property
    def is_readable(self) -> bool:
        """Return, if entity is readable."""
        return bool(self._attr_operations & OPERATION_READ)

    @value_property
    def is_valid(self) -> bool:
        """Return, if the value of the entity is valid based on the last updated datetime."""
        return self._attr_last_update > INIT_DATETIME

    @property
    def is_writeable(self) -> bool:
        """Return, if entity is writeable."""
        return bool(self._attr_operations & OPERATION_WRITE)

    @value_property
    def last_update(self) -> datetime:
        """Return the last updated datetime value."""
        return self._attr_last_update

    @value_property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return self._attr_state_uncertain

    @value_property
    def value(self) -> ParameterT | None:
        """Return the value of the entity."""
        return self._attr_value

    @property
    def supports_events(self) -> bool:
        """Return, if entity is supports events."""
        return bool(self._attr_operations & OPERATION_EVENT)

    @config_property
    def unit(self) -> str | None:
        """Return unit value."""
        return self._attr_unit

    @value_property
    def value_list(self) -> tuple[str, ...] | None:
        """Return the value_list."""
        return self._attr_value_list

    @property
    def visible(self) -> bool:
        """Return the if entity is visible in ccu."""
        return self._attr_visible

    def _fix_unit(self, raw_unit: str | None) -> str | None:
        """replace given unit."""
        if new_unit := FIX_UNIT_BY_PARAM.get(self._attr_parameter):
            return new_unit
        if not raw_unit:
            return None
        for (check, fix) in FIX_UNIT_REPLACE.items():
            if check in raw_unit:
                return fix
        return raw_unit

    @abstractmethod
    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""

    async def load_entity_value(
        self, call_source: HmCallSource, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Init the entity data."""
        if updated_within_seconds(
            last_update=self._attr_last_update, max_age_seconds=max_age_seconds
        ):
            return

        # Check, if entity is readable
        if not self.is_readable:
            return

        self.update_value(
            value=await self.device.value_cache.get_value(
                channel_address=self._attr_channel_address,
                paramset_key=self._attr_paramset_key,
                parameter=self._attr_parameter,
                call_source=call_source,
            )
        )

    def update_value(self, value: Any) -> None:
        """Update value of the entity."""
        if value == NO_CACHE_ENTRY:
            if self.last_update != INIT_DATETIME:
                self._attr_state_uncertain = True
                self.update_entity()
            return
        self._attr_value = self._convert_value(value)
        self._attr_state_uncertain = False
        self._set_last_update()
        self.update_entity()

    def update_parameter_data(self) -> None:
        """Update parameter data."""
        self._assign_parameter_data(
            parameter_data=self.device.central.paramset_descriptions.get_parameter_data(
                interface_id=self.device.interface_id,
                channel_address=self._attr_channel_address,
                paramset_key=self._attr_paramset_key,
                parameter=self._attr_parameter,
            )
        )

    def _convert_value(self, value: ParameterT) -> ParameterT:
        """Convert to value to ParameterT."""
        if value is None:
            return None
        try:
            if (
                self._attr_type == TYPE_BOOL
                and self._attr_value_list is not None
                and value is not None
                and isinstance(value, str)
            ):
                return convert_value(  # type: ignore[no-any-return]
                    value=self._attr_value_list.index(value),
                    target_type=self._attr_type,
                    value_list=self.value_list,
                )
            return convert_value(  # type: ignore[no-any-return]
                value=value, target_type=self._attr_type, value_list=self.value_list
            )
        except ValueError:
            _LOGGER.debug(
                "CONVERT_VALUE: conversion failed for %s, %s, %s, value: [%s]",
                self.device.interface_id,
                self._attr_channel_address,
                self._attr_parameter,
                value,
            )
            return None  # type: ignore[return-value]

    def get_event_data(self, value: Any = None) -> dict[str, Any]:
        """Get the event_data. #CC."""
        event_data = {
            ATTR_ADDRESS: self.device.device_address,
            ATTR_CHANNEL_NO: self._attr_channel_no,
            ATTR_DEVICE_TYPE: self.device.device_type,
            ATTR_INTERFACE_ID: self.device.interface_id,
            ATTR_PARAMETER: self._attr_parameter,
        }
        if value is not None:
            event_data[ATTR_VALUE] = value
        return cast(dict[str, Any], HM_EVENT_SCHEMA(event_data))

    def _set_last_update(self) -> None:
        """Set last_update to current datetime."""
        self._attr_last_update = datetime.now()


class GenericEntity(BaseParameterEntity[ParameterT]):
    """Base class for generic entities."""

    wrapped: bool = False

    @config_property
    def channel_operation_mode(self) -> str | None:
        """Return the channel operation mode if available."""
        cop: GenericEntity | None = self.device.generic_entities.get(
            (self._attr_channel_address, PARAM_CHANNEL_OPERATION_MODE)
        )
        if cop and cop.value:
            return str(cop.value)
        return None

    @property
    def _force_enabled(self) -> bool | None:
        """Return, if the entity/event must be enabled."""
        if self.channel_operation_mode is None:
            return None
        if (
            self._channel_type in CONFIGURABLE_CHANNEL
            and self._attr_parameter in CHANNEL_OPERATION_MODE_VISIBILITY
            and self.channel_operation_mode
            in CHANNEL_OPERATION_MODE_VISIBILITY[self._attr_parameter]
        ):
            return True
        return False

    def event(self, value: Any) -> None:
        """Handle event for which this entity has subscribed."""
        old_value = self._attr_value
        new_value = self._convert_value(value)
        if self._attr_value == new_value:
            return
        self.update_value(value=new_value)

        # reload paramset_descriptions, if value has changed
        if (
            self._attr_parameter == EVENT_CONFIG_PENDING
            and new_value is False
            and old_value is True
        ):
            self._central.create_task(self.device.reload_paramset_descriptions())

        # send device availability events
        if self._attr_parameter in (
            EVENT_UN_REACH,
            EVENT_STICKY_UN_REACH,
        ):
            self.device.update_device(self._attr_unique_identifier)

            if callable(self._central.callback_ha_event):
                self._central.callback_ha_event(
                    HmEventType.DEVICE_AVAILABILITY,
                    self.get_event_data(new_value),
                )

    async def send_value(
        self, value: Any, collector: CallParameterCollector | None = None
    ) -> None:
        """send value to ccu."""
        if collector:
            collector.add_entity(self, self._convert_value(value))
            return

        await self._client.set_value(
            channel_address=self._attr_channel_address,
            paramset_key=self._attr_paramset_key,
            parameter=self._attr_parameter,
            value=self._convert_value(value),
        )

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_entity_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            parameter=self._attr_parameter,
        )

    def _get_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        if self._central.parameter_visibility.parameter_is_hidden(
            device_type=self.device.device_type,
            device_channel=self.channel_no,
            paramset_key=self._attr_paramset_key,
            parameter=self._attr_parameter,
        ):
            return HmEntityUsage.ENTITY_NO_CREATE

        return (
            HmEntityUsage.ENTITY_NO_CREATE
            if self.device.has_custom_entity_definition
            else HmEntityUsage.ENTITY
        )


class WrapperEntity(BaseEntity):
    """Base class for entities that switch type of generic entities."""

    def __init__(self, wrapped_entity: GenericEntity, new_platform: HmPlatform) -> None:
        """Initialize the entity."""
        if wrapped_entity.platform == new_platform:
            raise HaHomematicException(
                "Cannot create wrapped entity. platform must not be equivalent."
            )
        self._wrapped_entity: Final[GenericEntity] = wrapped_entity
        super().__init__(
            device=wrapped_entity.device,
            channel_no=wrapped_entity.channel_no,
            unique_identifier=f"{wrapped_entity.unique_identifier}_{new_platform}",
        )
        self._attr_platform = new_platform
        # use callbacks from wrapped entity
        self._update_callbacks = wrapped_entity._update_callbacks
        self._remove_callbacks = wrapped_entity._remove_callbacks
        # hide wrapped entity from HA
        wrapped_entity.set_usage(HmEntityUsage.ENTITY_NO_CREATE)
        wrapped_entity.wrapped = True

    async def load_entity_value(
        self, call_source: HmCallSource, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Init the entity data."""
        await self._wrapped_entity.load_entity_value(
            call_source=call_source, max_age_seconds=max_age_seconds
        )

    def __getattr__(self, *args: Any) -> Any:
        """Return any other attribute not explicitly defined in the class."""
        return getattr(self._wrapped_entity, *args)

    def _get_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        return HmEntityUsage.ENTITY

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_entity_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            parameter=self._attr_parameter,
        )


_EntityT = TypeVar("_EntityT", bound=GenericEntity)


class CustomEntity(BaseEntity):
    """Base class for custom entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        device_enum: hmed.EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int | tuple[int, ...], tuple[str, ...]],
        channel_no: int,
        extended: hmed.ExtendedConfig | None = None,
    ) -> None:
        """Initialize the entity."""
        self._device_enum: Final[hmed.EntityDefinition] = device_enum
        # required for name in BaseEntity
        self._device_desc: Final[dict[str, Any]] = device_def
        self._entity_def: Final[dict[int | tuple[int, ...], tuple[str, ...]]] = entity_def
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_no=channel_no,
        )
        self._extended: Final[hmed.ExtendedConfig | None] = extended
        self.data_entities: dict[str, GenericEntity] = {}
        self._init_entities()
        self._init_entity_fields()

    @abstractmethod
    def _init_entity_fields(self) -> None:
        """Init the entity fields."""

    @value_property
    def last_update(self) -> datetime:
        """Return the latest last_update timestamp."""
        latest_update: datetime = INIT_DATETIME
        for entity in self._readable_entities:
            if (entity_last_update := entity.last_update) and entity_last_update > latest_update:
                latest_update = entity_last_update
        return latest_update

    @value_property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(entity.is_valid for entity in self._readable_entities)

    @value_property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(entity.state_uncertain for entity in self._readable_entities)

    @property
    def _readable_entities(self) -> list[GenericEntity]:
        """Returns the list of readable entities."""
        return [e for e in self.data_entities.values() if e.is_readable]

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        device_has_multiple_channels = hmce.is_multi_channel_device(
            device_type=self.device.device_type
        )
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel=self.channel_no,
            device_def=self._device_desc,
            device_has_multiple_channels=device_has_multiple_channels,
        )
        return get_custom_entity_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            is_only_primary_channel=is_only_primary_channel,
            usage=self._attr_usage,
        )

    def _get_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        if (
            secondary_channels := self._device_desc.get(hmed.ED_SECONDARY_CHANNELS)
        ) and self.channel_no in secondary_channels:
            return HmEntityUsage.CE_SECONDARY
        return HmEntityUsage.CE_PRIMARY

    async def load_entity_value(
        self, call_source: HmCallSource, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Init the entity values."""
        for entity in self.data_entities.values():
            if entity:
                await entity.load_entity_value(
                    call_source=call_source, max_age_seconds=max_age_seconds
                )
        self.update_entity()

    def _init_entities(self) -> None:
        """init entity collection."""
        # Add repeating fields
        for (field_name, parameter) in self._device_desc.get(
            hmed.ED_REPEATABLE_FIELDS, {}
        ).items():
            entity = self.device.get_generic_entity(
                channel_address=self._attr_channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity)

        # Add visible repeating fields
        for (field_name, parameter) in self._device_desc.get(
            hmed.ED_VISIBLE_REPEATABLE_FIELDS, {}
        ).items():
            entity = self.device.get_generic_entity(
                channel_address=self._attr_channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity, is_visible=True)

        if self._extended:
            if fixed_channels := self._extended.fixed_channels:
                for channel_no, mapping in fixed_channels.items():
                    for field_name, parameter in mapping.items():
                        channel_address = f"{self.device.device_address}:{channel_no}"
                        entity = self.device.get_generic_entity(
                            channel_address=channel_address, parameter=parameter
                        )
                        self._add_entity(field_name=field_name, entity=entity)
            if additional_entities := self._extended.additional_entities:
                self._mark_entities(entity_def=additional_entities)

        # Add device fields
        self._add_entities(
            field_dict_name=hmed.ED_FIELDS,
        )
        # Add visible device fields
        self._add_entities(
            field_dict_name=hmed.ED_VISIBLE_FIELDS,
            is_visible=True,
        )

        # Add default device entities
        self._mark_entities(entity_def=self._entity_def)
        # add default entities
        if hmed.get_include_default_entities(device_enum=self._device_enum):
            self._mark_entities(entity_def=hmed.get_default_entities())

        # add custom un_ignore entities
        self._mark_entity_by_custom_un_ignore_parameters(
            un_ignore_params_by_paramset_key=self._central.parameter_visibility.get_un_ignore_parameters(  # noqa: E501
                device_type=self.device.device_type, device_channel=self.channel_no
            )
        )

    def _add_entities(self, field_dict_name: str, is_visible: bool = False) -> None:
        """Add entities to custom entity."""
        fields = self._device_desc.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for (field_name, parameter) in channel.items():
                channel_address = f"{self.device.device_address}:{channel_no}"
                if entity := self.device.get_generic_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    if is_visible and entity.wrapped is False:
                        entity.set_usage(HmEntityUsage.CE_VISIBLE)
                    self._add_entity(field_name=field_name, entity=entity)

    def _add_entity(
        self, field_name: str, entity: GenericEntity | None, is_visible: bool = False
    ) -> None:
        """Add entity to collection and register callback."""
        if not entity:
            return

        if is_visible:
            entity.set_usage(HmEntityUsage.CE_VISIBLE)

        entity.register_update_callback(self.update_entity)
        self.data_entities[field_name] = entity

    def _mark_entities(self, entity_def: dict[int | tuple[int, ...], tuple[str, ...]]) -> None:
        """Mark entities to be created in HA."""
        if not entity_def:
            return
        for channel_nos, parameters in entity_def.items():
            if isinstance(channel_nos, int):
                self._mark_entity(channel_no=channel_nos, parameters=parameters)
            else:
                for channel_no in channel_nos:
                    self._mark_entity(channel_no=channel_no, parameters=parameters)

    def _mark_entity(self, channel_no: int, parameters: tuple[str, ...]) -> None:
        """Mark entity to be created in HA."""
        channel_address = f"{self.device.device_address}:{channel_no}"
        for parameter in parameters:
            entity = self.device.get_generic_entity(
                channel_address=channel_address, parameter=parameter
            )
            if entity:
                entity.set_usage(HmEntityUsage.ENTITY)

    def _mark_entity_by_custom_un_ignore_parameters(
        self, un_ignore_params_by_paramset_key: dict[str, tuple[str, ...]]
    ) -> None:
        """Mark entities to be created in HA."""
        if not un_ignore_params_by_paramset_key:
            return
        for paramset_key, un_ignore_params in un_ignore_params_by_paramset_key.items():
            for entity in self.device.generic_entities.values():
                if entity.paramset_key == paramset_key and entity.parameter in un_ignore_params:
                    entity.set_usage(HmEntityUsage.ENTITY)

    def _get_entity(self, field_name: str, entity_type: type[_EntityT]) -> _EntityT:
        """get entity."""
        if entity := self.data_entities.get(field_name):
            if not isinstance(entity, entity_type):
                _LOGGER.debug(
                    "GET_ENTITY: type mismatch for requested sub entity: "
                    "expected: %s, but is %s for field name %s of enitity %s",
                    entity_type.name,
                    type(entity),
                    field_name,
                    self.name,
                )
            return cast(entity_type, entity)  # type: ignore[valid-type]
        return cast(
            entity_type, NoneTypeEntity()  # type:ignore[valid-type]
        )


class GenericHubEntity(CallbackEntity):
    """Class for a HomeMatic system variable."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        address: str,
        data: HubData,
    ) -> None:
        """Initialize the entity."""
        unique_identifier: Final[str] = generate_unique_identifier(
            central=central,
            address=address,
            parameter=slugify(data.name),
        )
        super().__init__(unique_identifier=unique_identifier)
        self.central: Final[hmcu.CentralUnit] = central
        self._attr_name: Final[str] = self.get_name(data=data)
        self._attr_full_name: Final[str] = f"{self.central.name}_{self._attr_name}"

    @abstractmethod
    def get_name(self, data: HubData) -> str:
        """Return the name of the hub entity."""

    @config_property
    def full_name(self) -> str:
        """Return the fullname of the entity."""
        return self._attr_full_name

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._attr_name


class GenericSystemVariable(GenericHubEntity):
    """Class for a HomeMatic system variable."""

    _attr_is_extended = False

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: SystemVariableData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(central=central, address=SYSVAR_ADDRESS, data=data)
        self.ccu_var_name: Final[str] = data.name
        self.data_type: Final[str | None] = data.data_type
        self._attr_value_list: Final[tuple[str, ...] | None] = (
            tuple(data.value_list) if data.value_list else None
        )
        self._attr_max: Final[float | int | None] = data.max_value
        self._attr_min: Final[float | int | None] = data.min_value
        self._attr_unit: Final[str | None] = data.unit
        self._attr_value: bool | float | int | str | None = data.value

    @value_property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @value_property
    def value(self) -> Any | None:
        """Return the value."""
        return self._attr_value

    @value_property
    def value_list(self) -> tuple[str, ...] | None:
        """Return the value_list."""
        return self._attr_value_list

    @config_property
    def max(self) -> float | int | None:
        """Return the max value."""
        return self._attr_max

    @config_property
    def min(self) -> float | int | None:
        """Return the min value."""
        return self._attr_min

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the entity."""
        return self._attr_unit

    @property
    def is_extended(self) -> bool:
        """Return if the entity is an extended type."""
        return self._attr_is_extended

    def get_name(self, data: HubData) -> str:
        """Return the name of the sysvar entity."""
        if data.name.lower().startswith(tuple({"v_", "sv_"})):
            return data.name.title()
        return f"Sv_{data.name}".title()

    def update_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if self.data_type:
            value = parse_sys_var(data_type=self.data_type, raw_value=value)
        else:
            old_value = self._attr_value
            if isinstance(old_value, bool):
                value = bool(value)
            elif isinstance(old_value, int):
                value = int(value)
            elif isinstance(old_value, str):
                value = str(value)
            elif isinstance(old_value, float):
                value = float(value)

        if self._attr_value != value:
            self._attr_value = value
            self.update_entity()

    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if client := self.central.get_primary_client():
            await client.set_system_variable(
                name=self.ccu_var_name, value=parse_sys_var(self.data_type, value)
            )
        self.update_value(value=value)


class GenericEvent(BaseParameterEntity[Any]):
    """Base class for action events."""

    _attr_platform = HmPlatform.EVENT
    _attr_event_type: HmEventType

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ) -> None:
        """Initialize the event handler."""
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            paramset_key=PARAMSET_KEY_VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @config_property
    def event_type(self) -> HmEventType:
        """Return the event_type of the event."""
        return self._attr_event_type

    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""
        self.fire_event(value)

    def fire_event(self, value: Any) -> None:
        """Do what is needed to fire an event."""
        if callable(self._central.callback_ha_event):
            self._central.callback_ha_event(
                self.event_type,
                self.get_event_data(value=value),
            )

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_event_name(
            central=self._central,
            device=self.device,
            channel_no=self.channel_no,
            parameter=self._attr_parameter,
        )

    def _get_entity_usage(self) -> HmEntityUsage:
        """Generate the usage for the entity."""
        return HmEntityUsage.EVENT


class ClickEvent(GenericEvent):
    """class for handling click events."""

    _attr_event_type = HmEventType.KEYPRESS


class DeviceErrorEvent(GenericEvent):
    """class for handling device error events."""

    _attr_event_type = HmEventType.DEVICE_ERROR

    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""
        old_value = self._attr_value
        new_value = self._convert_value(value)
        if self._attr_value == new_value:
            return
        self.update_value(value=new_value)

        if isinstance(value, bool):
            if old_value is None and value is True:
                self.fire_event(value)
            elif isinstance(old_value, bool) and old_value != value:
                self.fire_event(value)
        if isinstance(value, int):
            if old_value is None and value > 0:
                self.fire_event(value)
            elif isinstance(old_value, int) and old_value != value:
                self.fire_event(value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    _attr_event_type = HmEventType.IMPULSE


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

    def send_value(self, value: Any) -> bool:
        """Send value dummy method."""
        return True


class CallParameterCollector:
    """Create a Paramset based on given generic entities."""

    def __init__(self, custom_entity: CustomEntity) -> None:
        """Init the generator."""
        self._custom_entity = custom_entity
        self._paramsets: dict[str, dict[str, Any]] = {}

    def add_entity(self, entity: GenericEntity, value: Any) -> None:
        """Add a generic entity."""
        # if entity.channel_address != self._custom_entity.channel_address:
        #    raise HaHomematicException(
        #        f"add_entity: Mismatch in channel_address for {self._custom_entity.full_name}"
        #    )
        if entity.channel_address not in self._paramsets:
            self._paramsets[entity.channel_address] = {}
        self._paramsets[entity.channel_address][entity.parameter] = value

    async def put_paramset(self) -> bool:
        """Send paramset to backend."""
        for channel_address, paramset in self._paramsets.items():
            if not await self._custom_entity.device.client.put_paramset(
                address=channel_address, paramset_key=PARAMSET_KEY_VALUES, value=paramset
            ):
                return False
        return True
