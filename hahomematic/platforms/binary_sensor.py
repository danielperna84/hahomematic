"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.decorators import value_property
from hahomematic.entity import GenericEntity, GenericSystemVariable

_LOGGER = logging.getLogger(__name__)


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


class HmSysvarBinarySensor(GenericSystemVariable):
    """
    Implementation of a sysvar binary_sensor.
    """

    _attr_platform = HmPlatform.HUB_BINARY_SENSOR

    @value_property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._attr_value is not None:
            return bool(self._attr_value)
        return None
