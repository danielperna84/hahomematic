"""Functions for event creation."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from hahomematic import support as hms
from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    ENTITY_EVENTS,
    IMPULSE_EVENTS,
    Description,
    EntityUsage,
    EventType,
    HmPlatform,
    Operations,
    ParamsetKey,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.decorators import config_property
from hahomematic.platforms.entity import BaseParameterEntity
from hahomematic.platforms.support import EntityNameData, generate_unique_id, get_event_name

_LOGGER: Final = logging.getLogger(__name__)


class GenericEvent(BaseParameterEntity[Any, Any]):
    """Base class for events."""

    _platform = HmPlatform.EVENT
    _event_type: EventType

    def __init__(
        self,
        device: hmd.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: Mapping[str, Any],
    ) -> None:
        """Initialize the event handler."""
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
            parameter_data=parameter_data,
        )

    @config_property
    def usage(self) -> EntityUsage:
        """Return the entity usage."""
        if (force_enabled := self._enabled_by_channel_operation_mode) is None:
            return self._usage
        return EntityUsage.EVENT if force_enabled else EntityUsage.NO_CREATE

    @config_property
    def event_type(self) -> EventType:
        """Return the event_type of the event."""
        return self._event_type

    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""
        if self.event_type in ENTITY_EVENTS:
            self.fire_update_entity_callback(parameter=self.parameter.lower())
        self.fire_event(value)

    def fire_event(self, value: Any) -> None:
        """Do what is needed to fire an event."""
        self._central.fire_ha_event_callback(
            event_type=self.event_type, event_data=self.get_event_data(value=value)
        )

    def _get_entity_name(self) -> EntityNameData:
        """Create the name for the entity."""
        return get_event_name(
            central=self._central,
            device=self._device,
            channel_no=self.channel_no,
            parameter=self._parameter,
        )

    def _get_entity_usage(self) -> EntityUsage:
        """Generate the usage for the entity."""
        return EntityUsage.EVENT


class ClickEvent(GenericEvent):
    """class for handling click events."""

    _event_type = EventType.KEYPRESS


class DeviceErrorEvent(GenericEvent):
    """class for handling device error events."""

    _event_type = EventType.DEVICE_ERROR

    def event(self, value: Any) -> None:
        """Handle event for which this handler has subscribed."""

        old_value, new_value = self.write_value(value=value)

        if (
            isinstance(new_value, bool)
            and (
                (old_value is None and new_value is True)
                or (isinstance(old_value, bool) and old_value != new_value)
            )
        ) or (
            isinstance(new_value, int)
            and (
                (old_value is None and new_value > 0)
                or (isinstance(old_value, int) and old_value != new_value)
            )
        ):
            self.fire_event(value=new_value)


class ImpulseEvent(GenericEvent):
    """class for handling impulse events."""

    _event_type = EventType.IMPULSE


def create_event_and_append_to_device(
    device: hmd.HmDevice, channel_address: str, parameter: str, parameter_data: Mapping[str, Any]
) -> None:
    """Create action event entity."""
    if device.central.parameter_visibility.parameter_is_ignored(
        device_type=device.device_type,
        channel_no=hms.get_channel_no(address=channel_address),
        paramset_key=ParamsetKey.VALUES,
        parameter=parameter,
    ):
        _LOGGER.debug(
            "create_event_and_append_to_device: Ignoring parameter: %s [%s]",
            parameter,
            channel_address,
        )
        return
    unique_id = generate_unique_id(
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
    if parameter_data[Description.OPERATIONS] & Operations.EVENT:
        if parameter in CLICK_EVENTS:
            event_t = ClickEvent
        if parameter.startswith(DEVICE_ERROR_EVENTS):
            event_t = DeviceErrorEvent
        if parameter in IMPULSE_EVENTS:
            event_t = ImpulseEvent
    if event_t:
        event = event_t(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        device.add_entity(event)
