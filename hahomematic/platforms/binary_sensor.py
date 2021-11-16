"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""

import logging

from hahomematic.const import HA_PLATFORM_BINARY_SENSOR
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmBinarySensor(GenericEntity):
    """
    Implementation of a binary_sensor.
    This is a default platform that gets automatically generated.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_BINARY_SENSOR,
        )

    @property
    def state(self):
        return self._state
