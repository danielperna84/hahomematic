"""
Module for entities implemented using the
number platform (https://www.home-assistant.io/integrations/number/).
"""

import logging

from hahomematic.const import ATTR_HM_VALUE, HA_PLATFORM_NUMBER
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmNumber(GenericEntity):
    """
    Implementation of a number.
    This is a default platform that gets automatically generated.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_NUMBER,
        )

    @property
    def state(self):
        """Get the state of the entity."""
        return self._state

    async def set_state(self, value):
        """Set the state of the entity."""
        # pylint: disable=no-else-return
        if self._min <= value <= self._max:
            await self.send_value(value)
            return
        elif self._special:
            if [sv for sv in self._special if value == sv[ATTR_HM_VALUE]]:
                await self.send_value(value)
                return
        _LOGGER.error(
            "number: Invalid value: %s (min: %s, max: %s, special: %s)",
            value,
            self._min,
            self._max,
            self._special,
        )
