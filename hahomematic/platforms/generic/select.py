"""
Module for entities implemented using the select platform.

See https://www.home-assistant.io/integrations/select/.
"""
from __future__ import annotations

from hahomematic.const import Platform
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.generic.entity import GenericEntity


class HmSelect(GenericEntity[int | str, int | str]):
    """
    Implementation of a select entity.

    This is a default platform that gets automatically generated.
    """

    _platform = Platform.SELECT

    @value_property
    def value(self) -> str | None:  # type: ignore[override]
        """Get the value of the entity."""
        if self._value is not None and self._value_list is not None:
            return self._value_list[int(self._value)]
        return str(self._default)

    def _prepare_value_for_sending(self, value: int | str, do_validate: bool = True) -> int | str:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int) and self._value_list and 0 <= value < len(self._value_list):
            return value
        if self._value_list and value in self._value_list:
            return self._value_list.index(value)
        raise ValueError(f"Value not in value_list for {self.name}/{self.unique_identifier}")
