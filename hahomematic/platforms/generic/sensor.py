"""
Module for entities implemented using the sensor platform.

See https://www.home-assistant.io/integrations/sensor/.
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import value_property

_LOGGER = logging.getLogger(__name__)


class HmSensor(GenericEntity[Any, None]):
    """
    Implementation of a sensor.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.SENSOR

    @value_property
    def value(self) -> Any | None:
        """Return the value."""
        if self._attr_value is not None and self._attr_value_list is not None:
            return self._attr_value_list[int(self._attr_value)]
        if convert_func := self._get_converter_func():
            return convert_func(self._attr_value)
        return self._attr_value

    def _get_converter_func(self) -> Any:
        """Return a converter based on sensor."""
        if convert_func := CONVERTERS_BY_PARAM.get(self.parameter):
            return convert_func
        return None


def _fix_rssi(value: Any) -> int | None:
    """
    Fix rssi value.

    See https://github.com/danielperna84/hahomematic/blob/devel/docs/rssi_fix.md.
    """
    if value is None or not isinstance(value, int):
        return None
    if -127 < value < 0:
        return value
    if 1 < value < 127:
        return value * -1
    if -256 < value < -129:
        return (value * -1) - 256
    if 129 < value < 256:
        return value - 256
    return None


CONVERTERS_BY_PARAM: dict[str, Any] = {
    "RSSI_PEER": _fix_rssi,
    "RSSI_DEVICE": _fix_rssi,
}
