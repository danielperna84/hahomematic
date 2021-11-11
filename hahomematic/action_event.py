# pylint: disable=line-too-long

"""
Functions for event handling.
"""

import datetime
import logging
from abc import ABC, abstractmethod

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_INTERFACE_ID,
    ATTR_NAME,
    ATTR_PARAMETER,
    ATTR_UNIQUE_ID,
    ATTR_VALUE,
    EVENT_CONFIG_PENDING,
    EVENT_IMPULSE,
    EVENT_KEYPRESS,
    EVENT_UN_REACH,
)
from hahomematic.helpers import get_entity_name

_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class BaseEvent(ABC):
    """Base class for action events"""

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, parameter, event_type):
        """
        Initialize the event handler.
        """
        self._device = device
        self._server = self._device.server
        self._interface_id = self._device.interface_id
        self.client = self._server.clients[self._interface_id]
        self.proxy = self.client.proxy
        self.unique_id = unique_id
        self.address = address
        self.parameter = parameter
        self.name = get_entity_name(
            server=self._server,
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
        ) not in self._server.entity_event_subscriptions:
            self._server.entity_event_subscriptions[(self.address, self.parameter)] = []
        self._server.entity_event_subscriptions[(self.address, self.parameter)].append(
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

        # fire an event, if the value changes
        old_value = self._value
        if self._value is not value:
            self._set_last_update()
            self._value = value
            self.fire_event(old_value, value)

    @property
    def value(self):
        """Return the value."""
        return self._value

    async def send_value(self, value) -> None:
        """send value to ccu."""
        try:
            await self.proxy.setValue(self.address, self.parameter, value)
        # pylint: disable=broad-except
        except Exception:
            _LOGGER.exception(
                "action_event: Failed to set state for: %s, %s, %s",
                self.address,
                self.parameter,
                value,
            )

    def add_to_collections(self) -> None:
        """add entity to server collections"""
        self._device.add_hm_action_event(self)

    def _set_last_update(self) -> None:
        self.last_update = datetime.datetime.now()

    @abstractmethod
    def fire_event(self, old_value, new_value) -> None:
        """
        Do what is needed to fire an event.
        """

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._server.entity_event_subscriptions[(self.address, self.parameter)]

    def _event_data(self, value):
        """Return the required event data."""
        return {
            ATTR_INTERFACE_ID: self._interface_id,
            ATTR_ADDRESS: self.address,
            ATTR_PARAMETER: self.parameter,
            ATTR_NAME: self.name,
            ATTR_UNIQUE_ID: self.unique_id,
            ATTR_VALUE: value,
        }


class ClickEvent(BaseEvent):
    """
    class for handling click events.
    """

    # pylint: disable=too-many-arguments
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

    def fire_event(self, old_value, new_value) -> None:
        """
        Do what is needed to fire an event.
        """
        # pylint: disable=not-callable
        if callable(self._server.callback_click_event):
            self._server.callback_click_event(
                self.event_type,
                self._event_data(new_value),
            )


class ImpulseEvent(BaseEvent):
    """
    class for handling impulse events.
    """

    # pylint: disable=too-many-arguments
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

    def fire_event(self, old_value, new_value) -> None:
        """
        Do what is needed to fire an event.
        """
        # pylint: disable=not-callable
        if self.parameter == EVENT_CONFIG_PENDING:
            if new_value is False and old_value is True:
                self._device.reload_paramsets()
            return
        if self.parameter == EVENT_UN_REACH:
            self._device.update_device(self.unique_id)
            return

        if callable(self._server.callback_impulse_event):
            self._server.callback_impulse_event(
                self.event_type,
                self._event_data(new_value),
            )
