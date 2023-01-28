"""Module for entities implemented using text."""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.entity import (
    CallParameterCollector,
    GenericEntity,
    GenericSystemVariable,
)


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


class HmSysvarText(GenericSystemVariable):
    """Implementation of a sysvar text entity."""

    _attr_platform = HmPlatform.HUB_TEXT
    _attr_is_extended = True

    async def send_variable(self, value: str | None) -> None:
        """Set the value of the entity."""
        await super().send_variable(value)
