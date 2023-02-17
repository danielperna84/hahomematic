"""Generic python representation of a CCU parameter."""
from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import (
    EVENT_CONFIG_PENDING,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    MAX_CACHE_AGE,
    HmCallSource,
    HmEntityUsage,
    HmEventType,
    HmPlatform,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd, entity as hme
from hahomematic.platforms.support import (
    EntityNameData,
    config_property,
    get_entity_name,
)

_LOGGER = logging.getLogger(__name__)


class GenericEntity(hme.BaseParameterEntity[hme.ParameterT, hme.InputParameterT]):
    """Base class for generic entities."""

    _attr_validate_state_change: bool = True

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_identifier: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ) -> None:
        """Init the generic entity."""
        super().__init__(
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        self.wrapped: bool = False

    @config_property
    def usage(self) -> HmEntityUsage:
        """Return the entity usage."""
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._attr_usage
        return HmEntityUsage.ENTITY if force_enabled else HmEntityUsage.ENTITY_NO_CREATE

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
        self,
        value: hme.InputParameterT,
        collector: hme.CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """send value to ccu, or use collector if set."""
        if not self.is_writeable:
            _LOGGER.error(
                "SEND_VALUE: writing to non-writable entity %s is not possible", self.full_name
            )
            return
        try:
            prepared_value = self._prepare_value_for_sending(value=value, do_validate=do_validate)
        except ValueError as verr:
            _LOGGER.warning(verr)
            return

        converted_value = self._convert_value(value=prepared_value)
        if collector:
            collector.add_entity(self, value=converted_value)
            return

        if self._attr_validate_state_change and not self.is_state_change(value=converted_value):
            return

        await self._client.set_value(
            channel_address=self._attr_channel_address,
            paramset_key=self._attr_paramset_key,
            parameter=self._attr_parameter,
            value=converted_value,
        )

    def _prepare_value_for_sending(
        self, value: hme.InputParameterT, do_validate: bool = True
    ) -> hme.ParameterT:
        """Prepare value, if required, before send."""
        return value  # type: ignore[return-value]

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
            channel_no=self.channel_no,
            paramset_key=self._attr_paramset_key,
            parameter=self._attr_parameter,
        ):
            return HmEntityUsage.ENTITY_NO_CREATE

        return (
            HmEntityUsage.ENTITY_NO_CREATE
            if self.device.has_custom_entity_definition
            else HmEntityUsage.ENTITY
        )

    def is_state_change(self, value: hme.ParameterT) -> bool:
        """
        Check if the state/value changes.

        If the state is uncertain, the state should also marked as changed.
        """
        if value != self._attr_value:
            return True
        if self.state_uncertain:
            return True
        _LOGGER.debug("NO_STATE_CHANGE: %s", self.name)
        return False


class WrapperEntity(hme.BaseEntity):
    """Base class for entities that switch type of generic entities."""

    def __init__(self, wrapped_entity: GenericEntity, new_platform: HmPlatform) -> None:
        """Initialize the entity."""
        if wrapped_entity.platform == new_platform:
            raise HaHomematicException(  # pragma: no cover
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
