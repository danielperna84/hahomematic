"""
Module for entities implemented using the
text platform (https://www.home-assistant.io/integrations/text/).
"""

import logging

from hahomematic.const import ATTR_HM_VALUE, HA_PLATFORM_TEXT
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HM_Text(GenericEntity):
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
    def STATE(self):
        return self._state

    @STATE.setter
    def STATE(self, value):
        # pylint: disable=no-else-return
        if self.min <= value <= self.max:
            self.send_value(value)
            return
        elif self.special:
            if [sv for sv in self.special if value == sv[ATTR_HM_VALUE]]:
                self.send_value(value)
                return
        LOG.error(
            "text: Invalid value: %s (min: %s, max: %s, special: %s)",
            value,
            self.min,
            self.max,
            self.special,
        )
