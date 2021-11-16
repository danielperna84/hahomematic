"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SELECT
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSelect(GenericEntity):
    """
    Implementation of a select.
    This is a default platform that gets automatically generated.
    """

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
        """Get the state of the entity."""
        if self._state:
            return self._value_list[self._state]
        return self._default

    async def set_state(self, value):
        # We allow setting the value via index as well, just in case.
        """Set the state of the entity."""
        if isinstance(value, int):
            await self.send_value(value)
        else:
            await self.send_value(self._value_list.index(value))
