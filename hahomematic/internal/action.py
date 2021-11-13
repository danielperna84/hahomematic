"""
Module for entities implemented actionx.
"""

import logging

from hahomematic.const import DATA_LOAD_SUCCESS, HA_PLATFORM_ACTION
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HmAction(GenericEntity):
    """
    Implementation of an action.
    This is an internal default platform that gets automatically generated.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_ACTION,
        )
        self.parameter = parameter

    @property
    def state(self):
        return self._state

    async def set_state(self, value):
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

    async def load_data(self) -> int:
        return DATA_LOAD_SUCCESS

    def add_to_collections(self) -> None:
        """add entity to server collections"""
        self._device.add_hm_entity(self)
