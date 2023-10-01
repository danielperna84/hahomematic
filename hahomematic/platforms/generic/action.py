"""
Module for action entities.

Actions are used to send data for write only parameters to backend.
There is no corresponding HA platform.
"""
from __future__ import annotations

from typing import Any

from hahomematic.const import Platform
from hahomematic.platforms.generic.entity import GenericEntity


class HmAction(GenericEntity[None, Any]):
    """
    Implementation of an action.

    This is an internal default platform that gets automatically generated.
    """

    _platform = Platform.ACTION
    _validate_state_change = False

    def _prepare_value_for_sending(self, value: Any, do_validate: bool = True) -> Any:
        """Prepare value before sending."""
        if (
            value is not None
            and self._value_list
            and isinstance(value, str)
            and value in self._value_list
        ):
            return self._value_list.index(value)
        return value
