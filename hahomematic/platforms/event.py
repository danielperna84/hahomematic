"""Functions for event creation."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    HM_OPERATIONS,
    IMPULSE_EVENTS,
    OPERATION_EVENT,
    PARAMSET_KEY_VALUES,
    HmEntityUsage,
    HmEventType,
    HmPlatform,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.entity import BaseParameterEntity
from hahomematic.platforms.support import (
    EntityNameData,
    config_property,
    generate_unique_identifier,
    get_event_name,
)

_LOGGER = logging.getLogger(__name__)


class GenericEvent(BaseParameterEntity[Any, Any]):
    """Base class for events."""

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
    def usage(self) -> HmEntityUsage:
        """Return the entity usage."""
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._attr_usage
        return HmEntityUsage.EVENT if force_enabled else HmEntityUsage.ENTITY_NO_CREATE

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

        if (
            isinstance(value, bool)
            and (
                (old_value is None and value is True)
                or (isinstance(old_value, bool) and old_value != value)
            )
        ) or (
            isinstance(value, int)
            and (
                (old_value is None and value > 0)
                or (isinstance(old_value, int) and old_value != value)
            )
        ):
            self.fire_event(value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    _attr_event_type = HmEventType.IMPULSE


def create_event_and_append_to_device(
    device: hmd.HmDevice, channel_address: str, parameter: str, parameter_data: dict[str, Any]
) -> None:
    """Create action event entity."""
    unique_identifier = generate_unique_identifier(
        central=device.central,
        address=channel_address,
        parameter=parameter,
        prefix=f"event_{device.central.name}",
    )

    _LOGGER.debug(
        "CREATE_EVENT_AND_APPEND_TO_DEVICE: Creating event for %s, %s, %s",
        channel_address,
        parameter,
        device.interface_id,
    )
    event_t: type[GenericEvent] | None = None
    if parameter_data[HM_OPERATIONS] & OPERATION_EVENT:
        if parameter in CLICK_EVENTS:
            event_t = ClickEvent
        if parameter.startswith(DEVICE_ERROR_EVENTS):
            event_t = DeviceErrorEvent
        if parameter in IMPULSE_EVENTS:
            event_t = ImpulseEvent
    if event_t:
        event = event_t(
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        device.add_entity(event)
