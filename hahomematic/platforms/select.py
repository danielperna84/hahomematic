"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""
from __future__ import annotations

import logging
from typing import Any, Union

import hahomematic.central_unit as hm_central
from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, GenericSystemVariable
from hahomematic.helpers import SystemVariableData

_LOGGER = logging.getLogger(__name__)


# pylint: disable=consider-alternative-union-syntax
class HmSelect(GenericEntity[Union[int, str]]):
    """
    Implementation of a select entity.
    This is a default platform that gets automatically generated.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        paramset_key: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.SELECT,
        )

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

    def __init__(self, central: hm_central.CentralUnit, data: SystemVariableData):
        """Initialize the entity."""
        super().__init__(central=central, data=data, platform=HmPlatform.HUB_SELECT)

    @property
    def value(self) -> str | None:
        """Get the value of the entity."""
        if self._value is not None and self._value_list is not None:
            return self._value_list[int(self._value)]
        return None

    async def send_variable(self, value: int | str) -> None:
        """Set the value of the entity."""
        # We allow setting the value via index as well, just in case.
        if isinstance(value, int):
            await super().send_variable(value)
        elif self._value_list:
            await super().send_variable(self._value_list.index(value))
