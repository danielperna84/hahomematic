"""
The base platform classes.
"""

import logging
from abc import ABC, abstractmethod

import hahomematic.data
from hahomematic.const import (
    ATTR_HM_CONTROL,
    ATTR_HM_ID,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE,
    ATTR_HM_VALUE_LIST,
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
        self.proxy = hahomematic.data.CLIENTS[interface_id]
        self.entity_id = entity_id.replace('-', '_').lower()
        self.unique_id = self.entity_id.split('.')[-1]
        self.address = address
        self.parameter = parameter
        self._parameter_data = parameter_data
        self.type = self._parameter_data.get(ATTR_HM_TYPE)
        self.control = self._parameter_data.get(ATTR_HM_CONTROL)
        self.name = hahomematic.data.NAMES.get(
            self.interface_id, {}).get(self.address, self.entity_id)
        self._state = None
        if self.type == TYPE_ACTION:
            self._state = False
        # Should we fetch the current value immediately if a `CONTROL` is set?

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
        if self._state is None:
            self._state = self.proxy.getValue(self.address, self.parameter)
        return self._state

class number(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "number.{}".format(unique_id),
                         address, parameter, parameter_data)
        self.unit = self._parameter_data.get(ATTR_HM_UNIT)
        self.max = self._parameter_data.get(ATTR_HM_MAX)
        self.min = self._parameter_data.get(ATTR_HM_MIN)
        self.value_list = dict(self._parameter_data.get(ATTR_HM_VALUE_LIST))
        self.special = self._parameter_data.get(ATTR_HM_SPECIAL)

    @property
    def STATE(self):
        if self._state is None:
            self._state = self.proxy.getValue(self.address, self.parameter)
        if self.type == TYPE_ENUM:
            return self.value_list[self._state]
        return self._state

    @STATE.setter
    def STATE(self, value):
        if self.type == TYPE_ENUM:
            if value in self.value_list:
                self.proxy.setValue(self.address, self.parameter, value)
                return
            LOG.error("number: Invalid value: %s (allowed: %s)",
                      value, self.value_list)
        else:
            if value >= self.min and value <= self.max:
                self.proxy.setValue(self.address, self.parameter, value)
                return
            elif self.special:
                for special_value in self.special:
                    if value == special_value[ATTR_HM_VALUE]:
                        self.proxy.setValue(self.address, self.parameter, value)
                        return
            LOG.error("number: Invalid value: %s (min: %s, max: %s, special: %s)",
                      value, self.min, self.max, self.special)

class sensor(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "sensor.{}".format(unique_id),
                         address, parameter, parameter_data)
        self.unit = self._parameter_data.get(ATTR_HM_UNIT)
        self.value_list = self._parameter_data.get(ATTR_HM_VALUE_LIST)

    @property
    def STATE(self):
        if self._state is None:
            self._state = self.proxy.getValue(self.address, self.parameter)
        if self.value_list:
            return self.value_list[self._state]
        return self._state

class switch(Entity):
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "switch.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        if self.type == TYPE_ACTION:
            return False
        if self._state is None:
            self._state = self.proxy.getValue(self.address, self.parameter)
        return self._state

    @STATE.setter
    def STATE(self, value):
        if self.type == TYPE_ACTION:
            self.proxy.setValue(self.address, self.parameter, True)
        else:
            self.proxy.setValue(self.address, self.parameter, value)
