"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.generic.entity import GenericEntity


class BaseNumber[NumberParameterT: int | float | None](
    GenericEntity[NumberParameterT, int | float | str]
):
    """
    Implementation of a number.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.NUMBER


class HmFloat(BaseNumber[float | None]):
    """
    Implementation of a Float.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(
        self, value: int | float | str, do_validate: bool = True
    ) -> float:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None
            and isinstance(value, int | float)
            and self._min <= float(value) <= self._max
        ):
            return float(value)
        if self._special and isinstance(value, str) and value in self._special:
            return float(self._special[value])
        raise ValueError(
            f"NUMBER.FLOAT failed: Invalid value: {value} (min: {self._min}, "
            f"max: {self._max}, special:{self._special})"
        )

    @value_property
    def value(self) -> float | None:  # type: ignore[override]
        """Return the value of the entity."""
        if self._value is not None:
            return self._value  # type: ignore[no-any-return]
        return self._default  # type: ignore[no-any-return]


class HmInteger(BaseNumber[int | None]):
    """
    Implementation of an Integer.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(
        self, value: int | float | str, do_validate: bool = True
    ) -> int:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None
            and isinstance(value, int | float)
            and self._min <= int(value) <= self._max
        ):
            return int(value)
        if self._special and isinstance(value, str) and value in self._special:
            return int(self._special[value])

        raise ValueError(
            f"NUMBER.INT failed: Invalid value: {value} (min: {self._min}, "
            f"max: {self._max}, special:{self._special})"
        )

    @value_property
    def value(self) -> int | None:  # type: ignore[override]
        """Return the value of the entity."""
        if self._value is not None:
            return self._value  # type: ignore[no-any-return]
        return self._default  # type: ignore[no-any-return]
