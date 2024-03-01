"""
Module for entities implemented using the select platform.

See https://www.home-assistant.io/integrations/select/.
"""

from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import get_value_from_value_list


class HmSelect(GenericEntity[int | str, int | float | str]):
    """
    Implementation of a select entity.

    This is a default platform that gets automatically generated.
    """

    _platform = HmPlatform.SELECT

    @value_property
    def value(self) -> str | None:  # type: ignore[override]
        """Get the value of the entity."""
        if (
            value := get_value_from_value_list(value=self._value, value_list=self.values)
        ) is not None:
            return value
        return str(self._default)

    def _prepare_value_for_sending(
        self, value: int | float | str, do_validate: bool = True
    ) -> int:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int | float) and self._values and 0 <= value < len(self._values):
            return int(value)
        if self._values and value in self._values:
            return self._values.index(value)
        raise ValueError(f"Value not in value_list for {self.name}/{self.unique_id}")
