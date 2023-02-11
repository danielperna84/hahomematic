"""
Module for hub entities implemented using the sensor platform.

See https://www.home-assistant.io/integrations/sensor/.
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import SYSVAR_TYPE_LIST, HmPlatform
from hahomematic.platforms.hub.entity import GenericSystemVariable
from hahomematic.platforms.support import value_property

_LOGGER = logging.getLogger(__name__)


class HmSysvarSensor(GenericSystemVariable):
    """Implementation of a sysvar sensor."""

    _attr_platform = HmPlatform.HUB_SENSOR

    @value_property
    def value(self) -> Any | None:
        """Return the value."""
        if (
            self.data_type == SYSVAR_TYPE_LIST
            and self._attr_value is not None
            and self.value_list is not None
        ):
            return self.value_list[int(self._attr_value)]
        return _check_length_and_warn(name=self.ccu_var_name, value=self._attr_value)


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
