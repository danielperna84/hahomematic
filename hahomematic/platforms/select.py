"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""
from __future__ import annotations

import logging
from typing import Union

from hahomematic.const import HmPlatform
from hahomematic.entity import GenericEntity, GenericSystemVariable

_LOGGER = logging.getLogger(__name__)


# pylint: disable=consider-alternative-union-syntax
class HmSelect(GenericEntity[Union[int, str]]):
    """
    Implementation of a select entity.
    This is a default platform that gets automatically generated.
    """

    _attr_platform = HmPlatform.SELECT

    @property
    def value(self) -> str | None:
        """Get the value of the entity."""
        if self._value is not None and self._value_list is not None:
            return self._value_list[int(self._value)]
        return str(self._default)

    async def send_value(self, value: int | str) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int):
            await super().send_value(value)
        elif self._value_list:
            await super().send_value(self._value_list.index(value))


class HmSysvarSelect(GenericSystemVariable):
    """
    Implementation of a sysvar select entity.
    """

    _attr_platform = HmPlatform.HUB_SELECT
    _attr_is_extended = True

    @property
    def value(self) -> str | None:
        """Get the value of the entity."""
        if self._value is not None and self.value_list is not None:
            return self.value_list[int(self._value)]
        return None

    async def send_variable(self, value: int | str) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int):
            await super().send_variable(value)
        elif self.value_list:
            await super().send_variable(self.value_list.index(value))
