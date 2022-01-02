"""
Module for entities implemented using the
switch platform (https://www.home-assistant.io/integrations/switch/).
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import TYPE_ACTION, HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSwitch(GenericEntity[bool]):
    """
    Implementation of a switch.
    This is a default platform that gets automatically generated.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.SWITCH,
        )

    @property
    def value(self) -> bool | None:
        """Get the value of the entity."""
        if self._type == TYPE_ACTION:
            return False
        return self._value

    async def turn_on(self) -> None:
        """Turn the switch on."""
        await self.send_value(True)

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self.send_value(False)
