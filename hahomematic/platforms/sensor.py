"""
Module for entities implemented using the
sensor platform (https://www.home-assistant.io/integrations/sensor/).
"""

import logging

from hahomematic.const import OPERATION_READ
from hahomematic.entity import Entity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class sensor(Entity):
    """
    Implementation of a sensor.
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
            "sensor",
        )

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
            if self._state is not None and self.value_list is not None:
                return self.value_list[self._state]
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "switch: Failed to get state for %s, %s, %s: %s",
                self.device_type,
                self.address,
                self.parameter,
                err,
            )
            return None
        return self._state
