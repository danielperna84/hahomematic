"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""
from __future__ import annotations

from hahomematic.const import HM_VALUE, HmPlatform
from hahomematic.platforms.entity import ParameterT
from hahomematic.platforms.generic.entity import GenericEntity


class BaseNumber(GenericEntity[ParameterT]):
    """
    Implementation of a number.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.NUMBER


class HmFloat(BaseNumber[float]):
    """
    Implementation of a Float.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(self, value: float, do_validate: bool = True) -> float:
        """Prepare value before sending."""
        if (
            not do_validate
            or (
                self._attr_special
                and [sv for sv in self._attr_special.values() if value == sv[HM_VALUE]]
            )
            or (value is not None and self._attr_min <= float(value) <= self._attr_max)
        ):
            return value
        raise ValueError(
            f"NUMBER.FLOAT failed: Invalid value: {value} (min: {self._attr_min}, "
            f"max: {self._attr_max}, special:{self._attr_special})"
        )


class HmInteger(BaseNumber[int]):
    """
    Implementation of an Integer.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(self, value: int, do_validate: bool = True) -> int:
        """Prepare value before sending."""
        if (
            value is not None and self._attr_min <= int(value) <= self._attr_max
        ) or not do_validate:
            return value
        if self._attr_special and [
            sv for sv in self._attr_special.values() if value == sv[HM_VALUE]
        ]:
            return value
        raise ValueError(
            f"NUMBER.INT failed: Invalid value: {value} (min: {self._attr_min}, "
            f"max: {self._attr_max}, special:{self._attr_special})"
        )
