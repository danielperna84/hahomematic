"""
Module for entities implemented using the
input_select platform (https://www.home-assistant.io/integrations/input_select/).
"""

import logging

from hahomematic.entity import Entity
from hahomematic.const import OPERATION_READ

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class input_select(Entity):
    """
    Implementation of a input_select.
    This is a default platform that gets automatically generated.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, "input_select.{}".format(unique_id),
                         address, parameter, parameter_data)

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info("input_select: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self.value_list[self._state]

    @STATE.setter
    def STATE(self, value):
        try:
            # We allow setting the value via index as well, just in case.
            if isinstance(value, int):
                self.proxy.setValue(self.address, self.parameter, value)
            else:
                self.proxy.setValue(self.address, self.parameter, self.value_list.index(value))
        # pylint: disable=broad-except
        except Exception:
            LOG.exception("input_select: Failed to set state for: %s, %s, %s, %s",
                          self.device_type, self.address, self.parameter, value)
