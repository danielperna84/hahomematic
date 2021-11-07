"""
Module for entities implemented using the
text platform (https://www.home-assistant.io/integrations/text/).
"""

import logging

from hahomematic.const import ATTR_HM_VALUE, HA_PLATFORM_TEXT
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HmText(GenericEntity):
    """
    Implementation of a text.
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
            platform=HA_PLATFORM_TEXT,
        )

    @property
    def state(self):
        return self._state

    @state.setter
    def state(self, value):
        # pylint: disable=no-else-return
        if self._min <= value <= self._max:
            self.send_value(value)
            return
        elif self._special:
            if [sv for sv in self._special if value == sv[ATTR_HM_VALUE]]:
                self.send_value(value)
                return
        _LOGGER.error(
            "text: Invalid value: %s (min: %s, max: %s, special: %s)",
            value,
            self._min,
            self._max,
            self._special,
        )
