"""
Module for entities implemented using the select platform.

See https://www.home-assistant.io/integrations/select/.
"""
from __future__ import annotations

from hahomematic.const import HmPlatform
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.support import value_property


class HmSelect(GenericEntity[int | str, int | str]):
    """
    Implementation of a select entity.

    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.SELECT

    @value_property
    def value(self) -> str | None:  # type: ignore[override]
        """Get the value of the entity."""
        if self._attr_value is not None and self._attr_value_list is not None:
            return self._attr_value_list[int(self._attr_value)]
        return str(self._attr_default)

    def _prepare_value_for_sending(self, value: int | str, do_validate: bool = True) -> int | str:
        """Prepare value before sending."""
        # We allow setting the value via index as well, just in case.
        if (
            isinstance(value, int)
            and self._attr_value_list
            and 0 <= value < len(self._attr_value_list)
        ):
            return value
        if self._attr_value_list and value in self._attr_value_list:
            return self._attr_value_list.index(value)
        raise ValueError(f"Value not in value_list for {self.name}/{self.unique_identifier}")
