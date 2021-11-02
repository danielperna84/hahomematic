"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SELECT
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HmSelect(GenericEntity):
    """
    Implementation of a select.
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
            platform=HA_PLATFORM_SELECT,
        )

    @property
    def state(self):
        return self._value_list[self._state]

    @state.setter
    def state(self, value):
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int):
            self.send_value(value)
        else:
            self.send_value(self._value_list.index(value))
