"""Module for entities implemented actions."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmAction(GenericEntity[None]):
    """
    Implementation of an action.
    This is an internal default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.ACTION

    async def send_value(self, value: Any) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if value is not None and self._value_list and isinstance(value, str):
            await super().send_value(self._value_list.index(value))
        else:
            await super().send_value(value)
