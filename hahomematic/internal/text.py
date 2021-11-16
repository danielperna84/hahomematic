"""Module for entities implemented using text."""

import logging

from hahomematic.const import ATTR_HM_VALUE, HA_PLATFORM_TEXT
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmText(GenericEntity):
    """
    Implementation of a text.
    This is an internal default platform that gets automatically generated.
    """

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
            "text: Invalid value: %s (min: %s, max: %s, special: %s)",
            value,
            self._min,
            self._max,
            self._special,
        )
