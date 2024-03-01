"""
Module for entities implemented using the button platform.

See https://www.home-assistant.io/integrations/boton/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.entity import GenericEntity


class HmButton(GenericEntity[None, bool]):
    """
    Implementation of a button.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.BUTTON
    _validate_state_change = False

    async def press(self) -> None:
        """Handle the button press."""
        await self.send_value(value=True)
