"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""
from __future__ import annotations

import logging

from hahomematic.const import HM_VALUE, HmPlatform
from hahomematic.entity import (
    CallParameterCollector,
    GenericEntity,
    GenericSystemVariable,
    ParameterT,
)

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

    async def send_value(
        self,
        value: float,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Set the value of the entity."""
        if (
            value is not None and self._attr_min <= float(value) <= self._attr_max
        ) or not do_validate:
            await super().send_value(value=value, collector=collector)
        elif self._attr_special:
            if [sv for sv in self._attr_special.values() if value == sv[HM_VALUE]]:
                await super().send_value(value=value, collector=collector)
        else:
            _LOGGER.warning(
                "NUMBER.FLOAT failed: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._attr_min,
                self._attr_max,
                self._attr_special,
            )


class HmInteger(BaseNumber[int]):
    """
    Implementation of an Integer.

    This is a default platform that gets automatically generated.
    """

    async def send_value(
        self, value: int, collector: CallParameterCollector | None = None, do_validate: bool = True
    ) -> None:
        """Set the value of the entity."""
        if (
            value is not None and self._attr_min <= int(value) <= self._attr_max
        ) or not do_validate:
            await super().send_value(value=value, collector=collector)
        elif self._attr_special:
            if [sv for sv in self._attr_special.values() if value == sv[HM_VALUE]]:
                await super().send_value(value=value, collector=collector)
        else:
            _LOGGER.warning(
                "NUMBER.INT failed: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._attr_min,
                self._attr_max,
                self._attr_special,
            )


class HmSysvarNumber(GenericSystemVariable):
    """Implementation of a sysvar number."""

    _attr_platform = HmPlatform.HUB_NUMBER
    _attr_is_extended = True

    async def send_variable(self, value: float) -> None:
        """Set the value of the entity."""
        if value is not None and self.max is not None and self.min is not None:
            if self.min <= float(value) <= self.max:
                await super().send_variable(value)
            else:
                _LOGGER.warning(
                    "SYSVAR.NUMBER failed: Invalid value: %s (min: %s, max: %s)",
                    value,
                    self.min,
                    self.max,
                )
            return
        await super().send_variable(value)
