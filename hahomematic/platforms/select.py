"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSelect(GenericEntity[int]):
    """
    Implementation of a select entity.
    This is a default platform that gets automatically generated.
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
            platform=HmPlatform.SELECT,
        )

    @property
    def value(self) -> str | None:
        """Get the state of the entity."""
        if self._value_list and self._state:
            return self._value_list[self._state]
        return None

    async def set_state(self, value: int | str) -> None:
        # We allow setting the value via index as well, just in case.
        """Set the state of the entity."""
        if isinstance(value, int):
            await self.send_value(value)
        elif self._value_list:
            await self.send_value(self._value_list.index(value))
