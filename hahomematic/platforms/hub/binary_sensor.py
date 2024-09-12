"""
Module for hub entities implemented using the binary_sensor platform.

See https://www.home-assistant.io/integrations/binary_sensor/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.hub.entity import GenericSystemVariable


class HmSysvarBinarySensor(GenericSystemVariable):
    """Implementation of a sysvar binary_sensor."""

    _platform = HmPlatform.HUB_BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._value is not None:
            return bool(self._value)
        return None
