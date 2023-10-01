"""
Module for hub entities implemented using the select platform.

See https://www.home-assistant.io/integrations/select/.
"""
from __future__ import annotations

import logging
from typing import Final

from hahomematic.const import Platform
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.hub.entity import GenericSystemVariable

_LOGGER: Final = logging.getLogger(__name__)


class HmSysvarSelect(GenericSystemVariable):
    """Implementation of a sysvar select entity."""

    _platform = Platform.HUB_SELECT
    _is_extended = True

    @value_property
    def value(self) -> str | None:
        """Get the value of the entity."""
        if self._value is not None and self._value_list is not None:
            return self._value_list[int(self._value)]
        return None

    async def send_variable(self, value: int | str) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int) and self._value_list:
            if 0 <= value < len(self._value_list):
                await super().send_variable(value)
        elif self._value_list:
            if value in self._value_list:
                await super().send_variable(self._value_list.index(value))
        else:
            _LOGGER.warning(
                "Value not in value_list for %s/%s",
                self.name,
                self.unique_identifier,
            )
