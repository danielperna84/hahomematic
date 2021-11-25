"""
Module for entities implemented using the
switch platform (https://www.home-assistant.io/integrations/switch/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SWITCH, TYPE_ACTION
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSwitch(GenericEntity):
    """
    Implementation of a switch.
    This is a default platform that gets automatically generated.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_SWITCH,
        )

    @property
    def state(self):
        """Get the state of the entity."""
        if self._type == TYPE_ACTION:
            return False

        return self._state

    async def turn_on(self) -> None:
        """Turn the switch on."""
        await self.send_value(True)

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self.send_value(False)

    async def set_state(self, value):
        """Set the state of the entity."""
        if self._type == TYPE_ACTION:
            await self.send_value(True)
        else:
            await self.send_value(value)
