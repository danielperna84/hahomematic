"""Module with base class for custom entities."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable, Mapping
from datetime import datetime
import logging
from typing import Any, Final, TypeVar, cast

from hahomematic.const import INIT_DATETIME, CallSource, EntityUsage
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.support import ExtendedConfig
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.entity import BaseEntity, CallParameterCollector
from hahomematic.platforms.generic import entity as hmge
from hahomematic.platforms.support import (
    EntityNameData,
    check_channel_is_the_only_primary_channel,
    get_custom_entity_name,
)
from hahomematic.support import get_channel_address

_LOGGER: Final = logging.getLogger(__name__)
_EntityT = TypeVar("_EntityT", bound=hmge.GenericEntity)


class CustomEntity(BaseEntity):
    """Base class for custom entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_id: str,
        device_profile: DeviceProfile,
        device_def: Mapping[str, Any],
        entity_def: Mapping[int | tuple[int, ...], tuple[str, ...]],
        channel_no: int,
        base_channel_no: int,
        extended: ExtendedConfig | None = None,
    ) -> None:
        """Initialize the entity."""
        self._device_profile: Final = device_profile
        # required for name in BaseEntity
        self._device_desc: Final = device_def
        self._entity_def: Final = entity_def
        self._base_channel_no: int = base_channel_no
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_no=channel_no,
            is_in_multiple_channels=hmed.is_multi_channel_device(device_type=device.device_type),
        )
        self._extended: Final = extended
        self._data_entities: Final[dict[Field, hmge.GenericEntity]] = {}
        self._init_entities()
        self._init_entity_fields()

    @config_property
    def base_channel_no(self) -> int | None:
        """Return the base channel no of the entity."""
        return self._base_channel_no

    @abstractmethod
    def _init_entity_fields(self) -> None:
        """Init the entity fields."""

    @value_property
    def last_updated(self) -> datetime:
        """Return the latest last_updated timestamp."""
        latest_update: datetime = INIT_DATETIME
        for entity in self._readable_entities:
            if (
                entity_last_updated := entity.last_updated
            ) and entity_last_updated > latest_update:
                latest_update = entity_last_updated
        return latest_update

    @value_property
    def last_refreshed(self) -> datetime:
        """Return the latest last_refreshed timestamp."""
        latest_refreshed: datetime = INIT_DATETIME
        for entity in self._readable_entities:
            if (
                entity_last_refreshed := entity.last_refreshed
            ) and entity_last_refreshed > latest_refreshed:
                latest_refreshed = entity_last_refreshed
        return latest_refreshed

    @property
    def has_data_entities(self) -> bool:
        """Return if there are data entities."""
        return len(self._data_entities) > 0

    @value_property
    def is_valid(self) -> bool:
        """Return if the state is valid."""
        return all(entity.is_valid for entity in self._relevant_entities)

    @value_property
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

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel_no=self.channel_no,
            device_def=self._device_desc,
            device_has_multiple_channels=self.is_in_multiple_channels,
        )
        return get_custom_entity_name(
            central=self._central,
            device=self._device,
            channel_no=self.channel_no,
            is_only_primary_channel=is_only_primary_channel,
            usage=self._usage,
        )

    def _get_entity_usage(self) -> EntityUsage:
        """Generate the usage for the entity."""
        if (
            secondary_channels := self._device_desc.get(hmed.ED.SECONDARY_CHANNELS)
        ) and self.channel_no in secondary_channels:
            return EntityUsage.CE_SECONDARY
        return EntityUsage.CE_PRIMARY

    async def load_entity_value(self, call_source: CallSource, direct_call: bool = False) -> None:
        """Init the entity values."""
        for entity in self._readable_entities:
            await entity.load_entity_value(call_source=call_source, direct_call=direct_call)
        self.fire_update_entity_callback()

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
        for field_name, parameter in self._device_desc.get(hmed.ED.REPEATABLE_FIELDS, {}).items():
            entity = self._device.get_generic_entity(
                channel_address=self._channel_address, parameter=parameter
            )
            self._add_entity(field=field_name, entity=entity)

        # Add visible repeating fields
        for field_name, parameter in self._device_desc.get(
            hmed.ED.VISIBLE_REPEATABLE_FIELDS, {}
        ).items():
            entity = self._device.get_generic_entity(
                channel_address=self._channel_address, parameter=parameter
            )
            self._add_entity(field=field_name, entity=entity, is_visible=True)

        if self._extended:
            if fixed_channels := self._extended.fixed_channels:
                for channel_no, mapping in fixed_channels.items():
                    for field_name, parameter in mapping.items():
                        channel_address = get_channel_address(
                            device_address=self._device.device_address, channel_no=channel_no
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

    def _add_entities(self, field_dict_name: hmed.ED, is_visible: bool = False) -> None:
        """Add entities to custom entity."""
        fields = self._device_desc.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for field, parameter in channel.items():
                channel_address = get_channel_address(
                    device_address=self._device.device_address, channel_no=channel_no
                )
                if entity := self._device.get_generic_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    if is_visible and entity.is_forced_sensor is False:
                        entity.set_usage(EntityUsage.CE_VISIBLE)
                    self._add_entity(field=field, entity=entity)

    def _add_entity(
        self, field: Field, entity: hmge.GenericEntity | None, is_visible: bool = False
    ) -> None:
        """Add entity to collection and register callback."""
        if not entity:
            return
        self.device.add_sub_device_channel(
            channel_no=self._channel_no, base_channel_no=self._base_channel_no
        )
        if is_visible:
            entity.set_usage(EntityUsage.CE_VISIBLE)

        entity.register_internal_update_callback(update_callback=self.fire_update_entity_callback)
        self._data_entities[field] = entity

    def unregister_update_callback(self, update_callback: Callable, custom_id: str) -> None:
        """Unregister update callback."""
        for entity in self._data_entities.values():
            entity.unregister_internal_update_callback(update_callback=update_callback)

        super().unregister_update_callback(update_callback=update_callback, custom_id=custom_id)

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
            device_address=self._device.device_address, channel_no=channel_no
        )

        for parameter in parameters:
            entity = self._device.get_generic_entity(
                channel_address=channel_address, parameter=parameter
            )
            if entity:
                entity.set_usage(EntityUsage.ENTITY)

    def _get_entity(self, field: Field, entity_type: type[_EntityT]) -> _EntityT:
        """Get entity."""
        if entity := self._data_entities.get(field):
            if not isinstance(entity, entity_type):
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
