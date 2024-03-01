"""
Module for entities implemented using the sensor platform.

See https://www.home-assistant.io/integrations/sensor/.
"""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any, Final

from hahomematic.const import HmPlatform, Parameter
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import get_value_from_value_list

_LOGGER: Final = logging.getLogger(__name__)


class HmSensor(GenericEntity[Any, None]):
    """
    Implementation of a sensor.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.SENSOR

    @value_property
    def value(self) -> Any:
        """Return the value."""
        if (
            value := get_value_from_value_list(value=self._value, value_list=self.values)
        ) is not None:
            return value
        if convert_func := self._get_converter_func():
            return convert_func(self._value)
        return self._value

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
    if value is None:
        return None
    if isinstance(value, int):
        if -127 < value < 0:
            return value
        if 1 < value < 127:
            return value * -1
        if -256 < value < -129:
            return (value * -1) - 256
        if 129 < value < 256:
            return value - 256
    return None


CONVERTERS_BY_PARAM: Mapping[str, Any] = {
    Parameter.RSSI_PEER: _fix_rssi,
    Parameter.RSSI_DEVICE: _fix_rssi,
}
