"""Module with base class for custom entities."""
from __future__ import annotations

from abc import abstractmethod
from datetime import datetime
import logging
from typing import Any, Final, TypeVar, cast

from hahomematic.const import INIT_DATETIME, MAX_CACHE_AGE, HmCallSource, HmEntityUsage
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import HmEntityDefinition
from hahomematic.platforms.custom.support import ExtendedConfig
from hahomematic.platforms.entity import BaseEntity
from hahomematic.platforms.generic import entity as hmge
from hahomematic.platforms.support import (
    EntityNameData,
    check_channel_is_the_only_primary_channel,
    get_custom_entity_name,
    value_property,
)
from hahomematic.support import get_channel_address

_EntityT = TypeVar("_EntityT", bound=hmge.GenericEntity)
_LOGGER = logging.getLogger(__name__)


class CustomEntity(BaseEntity):
    """Base class for custom entities."""

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        device_enum: HmEntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int | tuple[int, ...], tuple[str, ...]],
        channel_no: int,
        extended: ExtendedConfig | None = None,
    ) -> None:
        """Initialize the entity."""
        self._device_enum: Final[HmEntityDefinition] = device_enum
        # required for name in BaseEntity
        self._device_desc: Final[dict[str, Any]] = device_def
        self._entity_def: Final[dict[int | tuple[int, ...], tuple[str, ...]]] = entity_def
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_no=channel_no,
        )
        self._extended: Final[ExtendedConfig | None] = extended
        self.data_entities: dict[str, hmge.GenericEntity] = {}
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
    def _readable_entities(self) -> list[hmge.GenericEntity]:
        """Returns the list of readable entities."""
        return [e for e in self.data_entities.values() if e.is_readable]

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        device_has_multiple_channels = hmed.is_multi_channel_device(
            device_type=self.device.device_type
        )
        is_only_primary_channel = check_channel_is_the_only_primary_channel(
            current_channel_no=self.channel_no,
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
        """init entity collection."""
        # Add repeating fields
        for field_name, parameter in self._device_desc.get(hmed.ED_REPEATABLE_FIELDS, {}).items():
            entity = self.device.get_generic_entity(
                channel_address=self._attr_channel_address, parameter=parameter
            )
            self._add_entity(field_name=field_name, entity=entity)

        # Add visible repeating fields
        for field_name, parameter in self._device_desc.get(
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
                        channel_address = get_channel_address(
                            device_address=self.device.device_address, channel_no=channel_no
                        )
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
                device_type=self.device.device_type, channel_no=self.channel_no
            )
        )

    def _add_entities(self, field_dict_name: str, is_visible: bool = False) -> None:
        """Add entities to custom entity."""
        fields = self._device_desc.get(field_dict_name, {})
        for channel_no, channel in fields.items():
            for field_name, parameter in channel.items():
                channel_address = get_channel_address(
                    device_address=self.device.device_address, channel_no=channel_no
                )
                if entity := self.device.get_generic_entity(
                    channel_address=channel_address, parameter=parameter
                ):
                    if is_visible and entity.wrapped is False:
                        entity.set_usage(HmEntityUsage.CE_VISIBLE)
                    self._add_entity(field_name=field_name, entity=entity)

    def _add_entity(
        self, field_name: str, entity: hmge.GenericEntity | None, is_visible: bool = False
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

    def _mark_entity(self, channel_no: int | None, parameters: tuple[str, ...]) -> None:
        """Mark entity to be created in HA."""
        channel_address = get_channel_address(
            device_address=self.device.device_address, channel_no=channel_no
        )

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
            return  # pragma: no cover
        for paramset_key, un_ignore_params in un_ignore_params_by_paramset_key.items():
            for entity in self.device.generic_entities.values():
                if entity.paramset_key == paramset_key and entity.parameter in un_ignore_params:
                    entity.set_usage(HmEntityUsage.ENTITY)

    def _get_entity(self, field_name: str, entity_type: type[_EntityT]) -> _EntityT:
        """get entity."""
        if entity := self.data_entities.get(field_name):
            if not isinstance(entity, entity_type):
                _LOGGER.debug(  # pragma: no cover
                    "GET_ENTITY: type mismatch for requested sub entity: "
                    "expected: %s, but is %s for field name %s of entity %s",
                    entity_type.name,
                    type(entity),
                    field_name,
                    self.name,
                )
            return cast(entity_type, entity)  # type: ignore[valid-type]
        return cast(
            entity_type, NoneTypeEntity()  # type:ignore[valid-type]
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
    value_list: list[Any] = []
    visible: Any = None
    channel_operation_mode: str | None = None

    def send_value(self, value: Any) -> bool:
        """Send value dummy method."""
        return True  # pragma: no cover
