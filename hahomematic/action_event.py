"""Functions for event handling."""

from abc import ABC, abstractmethod
import datetime
import logging

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE_ID,
    ATTR_PARAMETER,
    ATTR_TYPE,
    ATTR_VALUE,
    EVENT_ALARM,
    EVENT_CONFIG_PENDING,
    EVENT_IMPULSE,
    EVENT_KEYPRESS,
    EVENT_UN_REACH,
)
from hahomematic.helpers import get_entity_name

_LOGGER = logging.getLogger(__name__)


class BaseEvent(ABC):
    """Base class for action events"""

    def __init__(self, device, unique_id, address, parameter, event_type):
        """
        Initialize the event handler.
        """
        self._device = device
        self._central = self._device.central
        self._interface_id = self._device.interface_id
        self.client = self._central.clients[self._interface_id]
        self.proxy = self.client.proxy
        self.unique_id = unique_id
        self.address = address
        self.parameter = parameter
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

    def __init__(self, device, unique_id, address, parameter):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            event_type=EVENT_ALARM,
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

    def __init__(self, device, unique_id, address, parameter):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            event_type=EVENT_KEYPRESS,
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

    def __init__(self, device, unique_id, address, parameter):
        """
        Initialize the event handler.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            event_type=EVENT_IMPULSE,
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
