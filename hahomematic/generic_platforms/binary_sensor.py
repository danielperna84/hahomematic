"""
Module for entities implemented using the binary_sensor platform.

See https://www.home-assistant.io/integrations/binary_sensor/.
"""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.entity_support import value_property
from hahomematic.generic_platforms.entity import GenericEntity


class HmBinarySensor(GenericEntity[bool]):
    """
    Implementation of a binary_sensor.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.BINARY_SENSOR

    @value_property
    def value(self) -> bool | None:  # type: ignore[override]
        """Return the value of the entity."""
        if self._attr_value is not None:
            return self._attr_value
        return self._attr_default
