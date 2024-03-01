"""
Module for action entities.

Actions are used to send data for write only parameters to backend.
There is no corresponding HA platform.
"""

from __future__ import annotations

from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import get_index_of_value_from_value_list


class HmAction(GenericEntity[None, Any]):
    """
    Implementation of an action.

    This is an internal default platform that gets automatically generated.
    """

    _platform = HmPlatform.ACTION
    _validate_state_change = False

    def _prepare_value_for_sending(self, value: Any, do_validate: bool = True) -> Any:
        """Prepare value before sending."""
        if (
            index := get_index_of_value_from_value_list(value=value, value_list=self._values)
        ) is not None:
            return index
        return value
