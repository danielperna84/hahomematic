"""
Module for entities implemented using the
number platform (https://www.home-assistant.io/integrations/number/).
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import ATTR_HM_VALUE, HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, ParameterType

_LOGGER = logging.getLogger(__name__)


class BaseNumber(GenericEntity[ParameterType]):
    """
    Implementation of a number.
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
            platform=HmPlatform.NUMBER,
        )


class HmFloat(BaseNumber[float]):
    """
    Implementation of a Float.
    This is a default platform that gets automatically generated.
    """

    async def send_value(self, value: float) -> None:
        """Set the value of the entity."""
        if value is not None and self._min <= float(value) <= self._max:
            await super().send_value(value)
        elif self._special:
            if [sv for sv in self._special.values() if value == sv[ATTR_HM_VALUE]]:
                await super().send_value(value)
        else:
            _LOGGER.error(
                "number.float: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._min,
                self._max,
                self._special,
            )


class HmInteger(BaseNumber[int]):
    """
    Implementation of an Integer.
    This is a default platform that gets automatically generated.
    """

    async def send_value(self, value: int) -> None:
        """Set the value of the entity."""
        if value is not None and self._min <= int(value) <= self._max:
            await super().send_value(value)
        elif self._special:
            if [sv for sv in self._special.values() if value == sv[ATTR_HM_VALUE]]:
                await super().send_value(value)
        else:
            _LOGGER.error(
                "number.int: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._min,
                self._max,
                self._special,
            )
