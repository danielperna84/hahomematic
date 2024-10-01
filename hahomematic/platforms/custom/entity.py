"""Module with base class for custom entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
import logging
from typing import Any, Final, cast

from hahomematic.const import CALLBACK_TYPE, ENTITY_KEY, INIT_DATETIME, CallSource, EntityUsage
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import ED, DeviceProfile, Field
from hahomematic.platforms.custom.support import CustomConfig
from hahomematic.platforms.decorators import get_service_calls, state_property
from hahomematic.platforms.entity import BaseEntity, CallParameterCollector
from hahomematic.platforms.generic import entity as hmge
from hahomematic.platforms.support import (
    EntityNameData,
    check_channel_is_the_only_primary_channel,
    get_custom_entity_name,
)
from hahomematic.support import get_channel_address

_LOGGER: Final = logging.getLogger(__name__)


class CustomEntity(BaseEntity):
    """Base class for custom entities."""

    def __init__(
        self,
        channel: hmd.HmChannel,
        unique_id: str,
        device_profile: DeviceProfile,
        device_def: Mapping[str, Any],
        entity_def: Mapping[int | tuple[int, ...], tuple[str, ...]],
        base_channel_no: int,
        custom_config: CustomConfig,
    ) -> None:
        """Initialize the entity."""
        self._unregister_callbacks: list[CALLBACK_TYPE] = []
        self._device_profile: Final = device_profile
        # required for name in BaseEntity
        self._device_def: Final = device_def
        self._entity_def: Final = entity_def
        self._base_no: int = base_channel_no
        self._custom_config: Final = custom_config
        self._extended: Final = custom_config.extended
        super().__init__(
            channel=channel,
            unique_id=unique_id,
            is_in_multiple_channels=hmed.is_multi_channel_device(
                model=channel.device.model, platform=self.platform
            ),
        )
        self._allow_undefined_generic_entities: Final[bool] = self._device_def[
            ED.ALLOW_UNDEFINED_GENERIC_ENTITIES
        ]
        self._data_entities: Final[dict[Field, hmge.GenericEntity]] = {}
        self._init_entities()
        self._init_entity_fields()
        self._service_methods = get_service_calls(obj=self)

    @property
    def allow_undefined_generic_entities(self) -> bool:
        """Return if undefined generic entities of this device are allowed."""
        return self._allow_undefined_generic_entities

    @property
    def base_no(self) -> int | None:
        """Return the base channel no of the entity."""
        return self._base_no

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        _LOGGER.debug(
            "INIT_ENTITY_FIELDS: Initialising the custom entity fields for %s", self.full_name
        )

    @state_property
    def modified_at(self) -> datetime:
        """Return the latest last update timestamp."""
        modified_at: datetime = INIT_DATETIME
        for entity in self._readable_entities:
            if (entity_modified_at := entity.modified_at) and entity_modified_at > modified_at:
                modified_at = entity_modified_at
        return modified_at

    @state_property
    def refreshed_at(self) -> datetime:
        """Return the latest last refresh timestamp."""
        refreshed_at: datetime = INIT_DATETIME
        for entity in self._readable_entities:
            if (entity_refreshed_at := entity.refreshed_at) and entity_refreshed_at > refreshed_at:
                refreshed_at = entity_refreshed_at
        return refreshed_at

    @property
    def unconfirmed_last_values_send(self) -> dict[Field, Any]:
        """Return the unconfirmed values send for the entity."""
        unconfirmed_values: dict[Field, Any] = {}
        for field, entity in self._data_entities.items():
            if (unconfirmed_value := entity.unconfirmed_last_value_send) is not None:
                unconfirmed_values[field] = unconfirmed_value
        return unconfirmed_values

    @property
    def has_data_entities(self) -> bool:
        """Return if there are data entities."""
        return len(self._data_entities) > 0

    @property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(entity.is_valid for entity in self._relevant_entities)

    @property
    def state_uncertain(self) -> bool:
        """Return, if the state is uncertain."""
        return any(entity.state_uncertain for entity in self._relevant_entities)

    @property
    def _readable_entities(self) -> tuple[hmge.GenericEntity, ...]:
        """Returns the list of readable entities."""
        return tuple(ge for ge in self._data_entities.values() if ge.is_readable)

    @property
    def _relevant_entities(self) -> tuple[hmge.GenericEntity, ...]:
        """Returns the list of relevant entities. To be overridden by subclasses."""
        return self._readable_entities

    @property
    def entity_name_postfix(self) -> str:
        """Return the entity name postfix."""
        return ""

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel_no=self._channel.no,
            device_def=self._device_def,
            device_has_multiple_channels=self.is_in_multiple_channels,
        )
        return get_custom_entity_name(
            channel=self._channel,
            is_only_primary_channel=is_only_primary_channel,
            usage=self._get_entity_usage(),
            postfix=self.entity_name_postfix.replace("_", " ").title(),
        )

    def _get_entity_usage(self) -> EntityUsage:
        """Generate the usage for the entity."""
        if self._forced_usage:
            return self._forced_usage
        if self._channel.no in self._custom_config.channels:
            return EntityUsage.CE_PRIMARY
        return EntityUsage.CE_SECONDARY

    async def load_entity_value(self, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the entity values."""
        for entity in self._readable_entities:
            await entity.load_entity_value(call_source=call_source, direct_call=direct_call)
        self.fire_entity_updated_callback()

    def is_state_change(self, **kwargs: Any) -> bool:
        """
        Check if the state changes due to kwargs.

        If the state is uncertain, the state should also marked as changed.
        """
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False

    def _init_entities(self) -> None:
        """Init entity collection."""
        # Add repeating fields
        for field_name, parameter in self._device_def.get(hmed.ED.REPEATABLE_FIELDS, {}).items():
            entity = self._device.get_generic_entity(
                channel_address=self._channel.address, parameter=parameter
            )
            self._add_entity(field=field_name, entity=entity, is_visible=False)

        # Add visible repeating fields
        for field_name, parameter in self._device_def.get(
            hmed.ED.VISIBLE_REPEATABLE_FIELDS, {}
        ).items():
            entity = self._device.get_generic_entity(
                channel_address=self._channel.address, parameter=parameter
            )
            self._add_entity(field=field_name, entity=entity, is_visible=True)

        if self._extended:
            if fixed_channels := self._extended.fixed_channels:
                for channel_no, mapping in fixed_channels.items():
                    for field_name, parameter in mapping.items():
                        channel_address = get_channel_address(
                            device_address=self._device.address, channel_no=channel_no
                        )
                        entity = self._device.get_generic_entity(
                            channel_address=channel_address, parameter=parameter
                        )
                        self._add_entity(field=field_name, entity=entity)
            if additional_entities := self._extended.additional_entities:
                self._mark_entities(entity_def=additional_entities)

        # Add device fields
        self._add_entities(
            field_dict_name=hmed.ED.FIELDS,
        )
        # Add visible device fields
        self._add_entities(
            field_dict_name=hmed.ED.VISIBLE_FIELDS,
            is_visible=True,
        )

        # Add default device entities
        self._mark_entities(entity_def=self._entity_def)
        # add default entities
        if hmed.get_include_default_entities(device_profile=self._device_profile):
            self._mark_entities(entity_def=hmed.get_default_entities())

    def _add_entities(self, field_dict_name: hmed.ED, is_visible: bool | None = None) -> None:
        """Add entities to custom entity."""
        fields = self._device_def.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for field, parameter in channel.items():
                channel_address = get_channel_address(
                    device_address=self._device.address, channel_no=channel_no
                )
                if entity := self._device.get_generic_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    self._add_entity(field=field, entity=entity, is_visible=is_visible)

    def _add_entity(
        self, field: Field, entity: hmge.GenericEntity | None, is_visible: bool | None = None
    ) -> None:
        """Add entity to collection and register callback."""
        if not entity:
            return
        if is_visible is True and entity.is_forced_sensor is False:
            entity.force_usage(forced_usage=EntityUsage.CE_VISIBLE)
        elif is_visible is False and entity.is_forced_sensor is False:
            entity.force_usage(forced_usage=EntityUsage.NO_CREATE)

        self._unregister_callbacks.append(
            entity.register_internal_entity_updated_callback(cb=self.fire_entity_updated_callback)
        )
        self._data_entities[field] = entity

    def _unregister_entity_updated_callback(self, cb: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        for unregister in self._unregister_callbacks:
            if unregister is not None:
                unregister()

        super()._unregister_entity_updated_callback(cb=cb, custom_id=custom_id)

    def _mark_entities(self, entity_def: Mapping[int | tuple[int, ...], tuple[str, ...]]) -> None:
        """Mark entities to be created in HA."""
        if not entity_def:
            return
        for channel_nos, parameters in entity_def.items():
            if isinstance(channel_nos, int):
                self._mark_entity(channel_no=channel_nos, parameters=parameters)
            else:
                for channel_no in channel_nos:
                    self._mark_entity(channel_no=channel_no, parameters=parameters)

    def _mark_entity(self, channel_no: int | None, parameters: tuple[str, ...]) -> None:
        """Mark entity to be created in HA."""
        channel_address = get_channel_address(
            device_address=self._device.address, channel_no=channel_no
        )

        for parameter in parameters:
            if entity := self._device.get_generic_entity(
                channel_address=channel_address, parameter=parameter
            ):
                entity.force_usage(forced_usage=EntityUsage.ENTITY)

    def _get_entity[_EntityT: hmge.GenericEntity](
        self, field: Field, entity_type: type[_EntityT]
    ) -> _EntityT:
        """Get entity."""
        if entity := self._data_entities.get(field):
            if type(entity).__name__ != entity_type.__name__:
                # not isinstance(entity, entity_type): # does not work with generic type
                _LOGGER.debug(  # pragma: no cover
                    "GET_ENTITY: type mismatch for requested sub entity: "
                    "expected: %s, but is %s for field name %s of entity %s",
                    entity_type.name,
                    type(entity),
                    field,
                    self.name,
                )
            return cast(entity_type, entity)  # type: ignore[valid-type]
        return cast(
            entity_type,  # type:ignore[valid-type]
            NoneTypeEntity(),
        )

    def has_entity_key(self, entity_keys: set[ENTITY_KEY]) -> bool:
        """Return if an entity with one of the entities is part of this entity."""
        result = [
            entity for entity in self._data_entities.values() if entity.entity_key in entity_keys
        ]
        return len(result) > 0


class NoneTypeEntity:
    """Entity to return an empty value."""

    default: Any = None
    hmtype: Any = None
    is_valid: bool = False
    max: Any = None
    min: Any = None
    unit: Any = None
    value: Any = None
    values: list[Any] = []
    visible: Any = None
    channel_operation_mode: str | None = None
    is_hmtype = False

    async def send_value(
        self,
        value: Any,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Send value dummy method."""
