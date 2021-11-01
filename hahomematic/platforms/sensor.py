"""
Module for entities implemented using the
sensor platform (https://www.home-assistant.io/integrations/sensor/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SENSOR
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HM_Sensor(GenericEntity):
    """
    Implementation of a sensor.
    This is a default platform that gets automatically generated.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_SENSOR,
        )

    @property
    def STATE(self):
        if self._state is not None and self.value_list is not None:
            return self.value_list[self._state]

        return self._state
