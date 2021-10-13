# pylint: disable=line-too-long

"""
Functions for entity creation.
"""

import logging
from abc import ABC, abstractmethod

from hahomematic import config, data
from hahomematic.const import (
    ATTR_HM_CONTROL,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE_LIST,
    HA_DOMAIN,
    TYPE_ACTION,
)

LOG = logging.getLogger(__name__)

# pylint: disable=too-many-instance-attributes
class Entity(ABC):
    """
    Base class for regular entities.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, interface_id, unique_id, address, parameter, parameter_data, platform
    ):
        """
        Initialize the entity.
        """
        self.interface_id = interface_id
        self.client = data.CLIENTS[interface_id]
        self.proxy = self.client.proxy
        self.unique_id = unique_id
        self.platform = platform
        self.address = address
        self._parent_address = address.split(":")[0]
        self._parent_device = data.DEVICES_RAW_DICT[interface_id][self._parent_address]
        self.device_type = self._parent_device.get(ATTR_HM_TYPE)
        self.parameter = parameter
        self._parameter_data = parameter_data
        self.operations = self._parameter_data.get(ATTR_HM_OPERATIONS)
        self.type = self._parameter_data.get(ATTR_HM_TYPE)
        self.control = self._parameter_data.get(ATTR_HM_CONTROL)
        self.unit = self._parameter_data.get(ATTR_HM_UNIT)
        self.max = self._parameter_data.get(ATTR_HM_MAX)
        self.min = self._parameter_data.get(ATTR_HM_MIN)
        self.value_list = self._parameter_data.get(ATTR_HM_VALUE_LIST)
        self.special = self._parameter_data.get(ATTR_HM_SPECIAL)
        self.device_class = None
        self.name = self.client.server.names_cache.get(self.interface_id, {}).get(
            self.address, self.unique_id
        )
        self._state = None
        if self.type == TYPE_ACTION:
            self._state = False
        LOG.debug("Entity.__init__: Getting current value for %s", self.unique_id)
        # pylint: disable=pointless-statement
        self.STATE
        data.EVENT_SUBSCRIPTIONS[(self.address, self.parameter)].append(self.event)
        self.update_callback = None
        if callable(config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = config.CALLBACK_ENTITY_UPDATE

    def event(self, interface_id, address, parameter, value):
        """
        Handle event for which this entity has subscribed.
        """
        LOG.debug(
            "Entity.event: %s, %s, %s, %s", interface_id, address, parameter, value
        )
        if interface_id != self.interface_id:
            LOG.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self.interface_id,
            )
            return
        if address != self.address:
            LOG.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                address,
                self.address,
            )
            return
        if parameter != self.parameter:
            LOG.warning(
                "Entity.event: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return
        self._state = value
        self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("Entity.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.unique_id)

    @property
    @abstractmethod
    # pylint: disable=invalid-name,missing-function-docstring
    def STATE(self):
        ...

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(HA_DOMAIN, self._parent_address)},
            "name": data.HA_DEVICES.get(self._parent_address).name,
            "manufacturer": "eQ-3",
            "model": self.device_type,
            "sw_version": self._parent_device.get("FIRMWARE"),
            "via_device": (HA_DOMAIN, self.interface_id),
        }
