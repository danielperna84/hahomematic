"""
Module for hub entities implemented using the sensor platform.

See https://www.home-assistant.io/integrations/sensor/.
"""

from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import HmPlatform, SysvarType
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.hub.entity import GenericSystemVariable
from hahomematic.platforms.support import get_value_from_value_list

_LOGGER: Final = logging.getLogger(__name__)


class HmSysvarSensor(GenericSystemVariable):
    """Implementation of a sysvar sensor."""

    _platform = HmPlatform.HUB_SENSOR

    @value_property
    def value(self) -> Any | None:
        """Return the value."""
        if (
            self.data_type == SysvarType.LIST
            and (value := get_value_from_value_list(value=self._value, value_list=self.values))
            is not None
        ):
            return value
        return _check_length_and_warn(name=self.ccu_var_name, value=self._value)


def _check_length_and_warn(name: str | None, value: Any) -> Any:
    """Check the length of a variable and warn if too long."""
    if isinstance(value, str) and len(value) > 255:
        _LOGGER.warning(
            "Value of sysvar %s exceedes maximum allowed length of "
            "255 chars by Home Assistant. Value will be limited to 255 chars",
            name,
        )
        return value[0:255:1]
    return value
