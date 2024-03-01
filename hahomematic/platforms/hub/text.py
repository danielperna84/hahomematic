"""
Module for hub entities implemented using the text platform.

See https://www.home-assistant.io/integrations/text/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.hub.entity import GenericSystemVariable


class HmSysvarText(GenericSystemVariable):
    """Implementation of a sysvar text entity."""

    _platform = HmPlatform.HUB_TEXT
    _is_extended = True

    async def send_variable(self, value: str | None) -> None:
        """Set the value of the entity."""
        await super().send_variable(value)
