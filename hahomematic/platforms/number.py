"""
Module for entities implemented using the
number platform (https://www.home-assistant.io/integrations/number/).
"""
from __future__ import annotations

import logging

from hahomematic.const import ATTR_HM_VALUE, HmPlatform
from hahomematic.entity import GenericEntity, GenericSystemVariable, ParameterT

_LOGGER = logging.getLogger(__name__)


class BaseNumber(GenericEntity[ParameterT]):
    """
    Implementation of a number.
    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.NUMBER


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
            _LOGGER.warning(
                "number.float failed: Invalid value: %s (min: %s, max: %s, special: %s)",
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
            _LOGGER.warning(
                "number.int failed: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._min,
                self._max,
                self._special,
            )


class HmSysvarNumber(GenericSystemVariable):
    """
    Implementation of a sysvar number.
    """

    _attr_platform = HmPlatform.HUB_NUMBER
    _attr_is_extended = True

    async def send_variable(self, value: float) -> None:
        """Set the value of the entity."""
        if value is not None and self.max is not None and self.min is not None:
            if self.min <= float(value) <= self.max:
                await super().send_variable(value)
            else:
                _LOGGER.warning(
                    "sysvar.number failed: Invalid value: %s (min: %s, max: %s)",
                    value,
                    self.min,
                    self.max,
                )
            return
        if value is not None:
            await super().send_variable(value)
