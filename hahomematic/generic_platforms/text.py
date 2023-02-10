"""
Module for entities implemented using the text platform.

See https://www.home-assistant.io/integrations/text/.
"""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.entity import CallParameterCollector
from hahomematic.generic_platforms.entity import GenericEntity


class HmText(GenericEntity[str]):
    """
    Implementation of a text.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.TEXT

    async def send_value(
        self, value: str | None, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the value of the entity."""
        await super().send_value(value=value, collector=collector)
