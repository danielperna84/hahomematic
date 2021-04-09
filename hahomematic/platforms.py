"""
The base platform classes.
"""

import logging
from abc import ABC, abstractmethod

import hahomematic.data
import hahomematic.config
from hahomematic.const import (
    ATTR_HM_CONTROL,
    ATTR_HM_ID,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_OPERATIONS,
    ATTR_HM_PARENT_TYPE,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE,
    ATTR_HM_VALUE_LIST,
    OPERATION_READ,
    TYPE_ACTION,
    TYPE_ENUM,
)

LOG = logging.getLogger(__name__)

class Entity(ABC):
    """
    Base class for regular entities.
    """
    def __init__(self, interface_id, entity_id, address, parameter, parameter_data):
        """
        Initialize the entity.
        """
        self.interface_id = interface_id
        self.client = hahomematic.data.CLIENTS[interface_id]
        self.proxy = self.client.proxy
        self.entity_id = entity_id.replace('-', '_').lower()
        self.unique_id = self.entity_id.split('.')[-1]
        self.address = address
        self.device_type = hahomematic.data.DEVICES_RAW_DICT[self.interface_id][self.address].get(ATTR_HM_PARENT_TYPE)
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
        self.name = hahomematic.data.NAMES.get(
            self.interface_id, {}).get(self.address, self.entity_id)
        self._state = None
        if self.type == TYPE_ACTION:
            self._state = False
        LOG.debug("Entity.__init__: Getting current value for %s",
                  self.entity_id)
        self.STATE
        hahomematic.data.EVENT_SUBSCRIPTIONS[(self.address, self.parameter)].append(self.event)
        self.update_callback = None
        if callable(hahomematic.config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = hahomematic.config.CALLBACK_ENTITY_UPDATE

    def event(self, interface_id, address, parameter, value):
        """
        Handle event for which this entity has subscribed.
        """
        LOG.debug("Entity.event: %s, %s, %s, %s",
                  interface_id, address, parameter, value)
        if interface_id != self.interface_id:
            LOG.warning("Entity.event: Incorrect interface_id: %s - should be: %s",
                        interface_id, self.interface_id)
            return
        if address != self.address:
            LOG.warning("Entity.event: Incorrect address: %s - should be: %s",
                        address, self.address)
            return
        if parameter != self.parameter:
            LOG.warning("Entity.event: Incorrect parameter: %s - should be: %s",
                        parameter, self.parameter)
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
        self.update_callback(self.entity_id)

    @property
    @abstractmethod
    def STATE(self):
        ...

class binary_sensor(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "binary_sensor.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        except Exception as err:
            LOG.info("binary_sensor: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

class input_select(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "input_select.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.value_list[self.proxy.getValue(self.address, self.parameter)]
        except Exception as err:
            LOG.info("input_select: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

    @STATE.setter
    def STATE(self, value):
        try:
            self.proxy.setValue(self.address, self.parameter, self.value_list.index(value))
        except Exception:
            LOG.exception("input_select: Failed to set state for: %s, %s, %s, %s",
                          self.device_type, self.address, self.parameter, value)

class input_text(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "input_text.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        except Exception as err:
            LOG.info("input_text: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

    @STATE.setter
    def STATE(self, value):
        try:
            self.proxy.setValue(self.address, self.parameter, str(value))
        except Exception:
            LOG.exception("input_text: Failed to set state for: %s, %s, %s, %s",
                          self.device_type, self.address, self.parameter, value)

class number(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "number.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        except Exception as err:
            LOG.info("number: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

    @STATE.setter
    def STATE(self, value):
        try:
            if value >= self.min and value <= self.max:
                self.proxy.setValue(self.address, self.parameter, value)
                return
            elif self.special:
                if [sv for sv in self.special if value == sv[ATTR_HM_VALUE]]:
                    self.proxy.setValue(self.address, self.parameter, value)
                    return
            LOG.error("number: Invalid value: %s (min: %s, max: %s, special: %s)",
                        value, self.min, self.max, self.special)
        except Exception:
            LOG.exception("number: Failed to set state for %s, %s, %s, %s",
                          self.device_type, self.address, self.parameter, value)

class sensor(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "sensor.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
            if self._state is not None and self.value_list is not None:
                return self.value_list[self._state]
        except Exception as err:
            LOG.info("switch: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

class switch(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "switch.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        if self.type == TYPE_ACTION:
            return False
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        except Exception as err:
            LOG.info("switch: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state

    @STATE.setter
    def STATE(self, value):
        try:
            if self.type == TYPE_ACTION:
                self.proxy.setValue(self.address, self.parameter, True)
            else:
                self.proxy.setValue(self.address, self.parameter, value)
        except Exception:
            LOG.exception("switch: Failed to set state for: %s, %s, %s, %s",
                          self.device_type, self.address, self.parameter, value)
