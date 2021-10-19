"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""

import logging

from hahomematic.const import HA_PLATFORM_BINARY_SENSOR, OPERATION_READ
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class Binary_Sensor(GenericEntity):
    """
    Implementation of a binary_sensor.
    This is a default platform that gets automatically generated.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, server, interface_id, unique_id, address, parameter, parameter_data
    ):
        super().__init__(
            server,
            interface_id,
            unique_id,
            address,
            parameter,
            parameter_data,
            HA_PLATFORM_BINARY_SENSOR,
        )

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "binary_sensor: Failed to get state for %s, %s, %s: %s",
                self.device_type,
                self.address,
                self.parameter,
                err,
            )
            return None
        return self._state
