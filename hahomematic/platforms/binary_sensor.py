"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""

import logging

from hahomematic.entity import Entity
from hahomematic.const import OPERATION_READ

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class binary_sensor(Entity):
    """
    Implementation of a binary_sensor.
    This is a default platform that gets automatically generated.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, unique_id, address, parameter, parameter_data):
        super().__init__(interface_id, unique_id, address, parameter, parameter_data, 'binary_sensor')

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info("binary_sensor: Failed to get state for %s, %s, %s: %s",
                     self.device_type, self.address, self.parameter, err)
            return None
        return self._state
