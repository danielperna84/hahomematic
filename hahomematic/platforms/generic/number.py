"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.entity import InputParameterT, ParameterT
from hahomematic.platforms.generic.entity import GenericEntity


class BaseNumber(GenericEntity[ParameterT, InputParameterT]):
    """
    Implementation of a number.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.NUMBER


class HmFloat(BaseNumber[float, float | str]):
    """
    Implementation of a Float.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(self, value: float | str, do_validate: bool = True) -> float:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None
            and isinstance(value, float)
            and self._min <= float(value) <= self._max
        ):
            return float(value)
        if self._special and isinstance(value, str) and value in self._special:
            return float(self._special[value])
        raise ValueError(
            f"NUMBER.FLOAT failed: Invalid value: {value} (min: {self._min}, "
            f"max: {self._max}, special:{self._special})"
        )


class HmInteger(BaseNumber[int, int | str]):
    """
    Implementation of an Integer.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(self, value: int | str, do_validate: bool = True) -> int:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None and isinstance(value, int) and self._min <= int(value) <= self._max
        ):
            return int(value)
        if self._special and isinstance(value, str) and value in self._special:
            return int(self._special[value])

        raise ValueError(
            f"NUMBER.INT failed: Invalid value: {value} (min: {self._min}, "
            f"max: {self._max}, special:{self._special})"
        )
