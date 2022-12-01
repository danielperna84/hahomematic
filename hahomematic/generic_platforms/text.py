"""Module for entities implemented using text."""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmText(GenericEntity[str]):
    """
    Implementation of a text.
    This is an internal default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.TEXT

    async def send_value(self, value: str | None) -> None:
        """Set the value of the entity."""
        await super().send_value(value)
