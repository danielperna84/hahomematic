"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SELECT
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HM_Select(GenericEntity):
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
    def STATE(self):
        return self.value_list[self._state]

    @STATE.setter
    def STATE(self, value):
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int):
            self.send_value(value)
        else:
            self.send_value(self.value_list.index(value))
