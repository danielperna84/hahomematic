"""
Module for entities implemented using the number platform.

See https://www.home-assistant.io/integrations/number/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.generic.entity import GenericEntity


class BaseNumber[NumberParameterT: int | float | None](
    GenericEntity[NumberParameterT, int | float | str]
):
    """
    Implementation of a number.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.NUMBER

    def _prepare_number_for_sending(
        self, value: int | float | str, type_converter: type, do_validate: bool = True
    ) -> NumberParameterT:
        """Prepare value before sending."""
        if not do_validate or (
            value is not None
            and isinstance(value, int | float)
            and self._min <= type_converter(value) <= self._max
        ):
            return type_converter(value)  # type: ignore[no-any-return]
        if self._special and isinstance(value, str) and value in self._special:
            return type_converter(self._special[value])  # type: ignore[no-any-return]
        raise ValueError(
            f"NUMBER failed: Invalid value: {value} (min: {self._min}, "
            f"max: {self._max}, special:{self._special})"
        )


class HmFloat(BaseNumber[float | None]):
    """
    Implementation of a Float.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(
        self, value: int | float | str, do_validate: bool = True
    ) -> float | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(
            value=value, type_converter=float, do_validate=do_validate
        )

    @state_property
    def value(self) -> float | None:  # type: ignore[override]
        """Return the value of the entity."""
        return self._value  # type: ignore[no-any-return]


class HmInteger(BaseNumber[int | None]):
    """
    Implementation of an Integer.

    This is a default platform that gets automatically generated.
    """

    def _prepare_value_for_sending(
        self, value: int | float | str, do_validate: bool = True
    ) -> int | None:
        """Prepare value before sending."""
        return self._prepare_number_for_sending(
            value=value, type_converter=int, do_validate=do_validate
        )

    @state_property
    def value(self) -> int | None:  # type: ignore[override]
        """Return the value of the entity."""
        return self._value  # type: ignore[no-any-return]
