"""
Module for entities implemented using the
sensor platform (https://www.home-assistant.io/integrations/sensor/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SENSOR
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSensor(GenericEntity):
    """
    Implementation of a sensor.
    This is a default platform that gets automatically generated.
    """

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
    def state(self):
        if self._state is not None and self._value_list is not None:
            return self._value_list[self._state]

        return self._state
