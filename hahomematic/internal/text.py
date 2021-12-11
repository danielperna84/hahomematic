"""Module for entities implemented using text."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmText(GenericEntity[str]):
    """
    Implementation of a text.
    This is an internal default platform that gets automatically generated.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.TEXT,
        )

    @property
    def state(self) -> str | None:
        """Get the state of the entity."""
        return self._state

    async def set_state(self, value: str | None) -> None:
        """Set the state of the entity."""
        await self.send_value(value)
