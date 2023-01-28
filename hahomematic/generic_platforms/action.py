"""
Module for action entities.

Actions are used to send data for write only parameters to backend.
There is no corresponding HA platform.
"""
from __future__ import annotations

from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.entity import CallParameterCollector, GenericEntity


class HmAction(GenericEntity[None]):
    """
    Implementation of an action.

    This is an internal default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.ACTION

    async def send_value(
        self, value: Any, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if value is not None and self._attr_value_list and isinstance(value, str):
            await super().send_value(value=self._attr_value_list.index(value), collector=collector)
        else:
            await super().send_value(value=value, collector=collector)
