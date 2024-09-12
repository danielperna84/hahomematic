"""
Module for entities implemented using the binary_sensor platform.

See https://www.home-assistant.io/integrations/binary_sensor/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.generic.entity import GenericEntity


class HmBinarySensor(GenericEntity[bool | None, bool]):
    """
    Implementation of a binary_sensor.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.BINARY_SENSOR

    @state_property
    def value(self) -> bool | None:  # type: ignore[override]
        """Return the value of the entity."""
        if self._value is not None:
            return self._value  # type: ignore[no-any-return]
        return self._default  # type: ignore[no-any-return]
