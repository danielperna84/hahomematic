"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.platforms.hub.entity import GenericSystemVariable

_LOGGER = logging.getLogger(__name__)


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
