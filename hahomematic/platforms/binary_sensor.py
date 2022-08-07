"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""
from __future__ import annotations

import logging

from hahomematic.const import HmPlatform
from hahomematic.entity import GenericEntity, GenericSystemVariable

_LOGGER = logging.getLogger(__name__)


class HmBinarySensor(GenericEntity[bool]):
    """
    Implementation of a binary_sensor.
    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.BINARY_SENSOR

    @property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._value is not None:
            return self._value
        return self._default


class HmSysvarBinarySensor(GenericSystemVariable):
    """
    Implementation of a sysvar binary_sensor.
    """

    _attr_platform = HmPlatform.HUB_BINARY_SENSOR

    @property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._value is not None:
            return bool(self._value)
        return None
