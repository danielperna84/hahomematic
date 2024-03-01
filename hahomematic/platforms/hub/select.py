"""
Module for hub entities implemented using the select platform.

See https://www.home-assistant.io/integrations/select/.
"""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.hub.entity import GenericSystemVariable
from hahomematic.platforms.support import get_value_from_value_list

_LOGGER: Final = logging.getLogger(__name__)


class HmSysvarSelect(GenericSystemVariable):
    """Implementation of a sysvar select entity."""

    _platform = HmPlatform.HUB_SELECT
    _is_extended = True

    @value_property
    def value(self) -> str | None:
        """Get the value of the entity."""
        if (
            value := get_value_from_value_list(value=self._value, value_list=self.values)
        ) is not None:
            return value
        return None

    async def send_variable(self, value: int | str) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int) and self._values:
            if 0 <= value < len(self._values):
                await super().send_variable(value)
        elif self._values:
            if value in self._values:
                await super().send_variable(self._values.index(value))
        else:
            _LOGGER.warning(
                "Value not in value_list for %s/%s",
                self.name,
                self.unique_id,
            )
