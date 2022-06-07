"""
Module for entities implemented using the
number platform (https://www.home-assistant.io/integrations/number/).
"""
from __future__ import annotations

import logging
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import ATTR_HM_VALUE, HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, GenericSystemVariable, ParameterT
from hahomematic.helpers import SystemVariableData

_LOGGER = logging.getLogger(__name__)


class BaseNumber(GenericEntity[ParameterT]):
    """
    Implementation of a number.
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
            platform=HmPlatform.NUMBER,
        )


class HmFloat(BaseNumber[float]):
    """
    Implementation of a Float.
    This is a default platform that gets automatically generated.
    """

    async def send_value(self, value: float) -> None:
        """Set the value of the entity."""
        if value is not None and self._min <= float(value) <= self._max:
            await super().send_value(value)
        elif self._special:
            if [sv for sv in self._special.values() if value == sv[ATTR_HM_VALUE]]:
                await super().send_value(value)
        else:
            _LOGGER.warning(
                "number.float: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._min,
                self._max,
                self._special,
            )


class HmInteger(BaseNumber[int]):
    """
    Implementation of an Integer.
    This is a default platform that gets automatically generated.
    """

    async def send_value(self, value: int) -> None:
        """Set the value of the entity."""
        if value is not None and self._min <= int(value) <= self._max:
            await super().send_value(value)
        elif self._special:
            if [sv for sv in self._special.values() if value == sv[ATTR_HM_VALUE]]:
                await super().send_value(value)
        else:
            _LOGGER.warning(
                "number.int: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self._min,
                self._max,
                self._special,
            )


class HmSysvarNumber(GenericSystemVariable):
    """
    Implementation of a sysvar number.
    """

    def __init__(self, central: hm_central.CentralUnit, data: SystemVariableData):
        """Initialize the entity."""
        super().__init__(central=central, data=data, platform=HmPlatform.HUB_NUMBER)

    async def send_variable(self, value: float) -> None:
        """Set the value of the entity."""
        if value is not None and self._max is not None and self._min is not None:
            if self._min <= float(value) <= self._max:
                await super().send_variable(value)
            else:
                _LOGGER.warning(
                    "sysvar.number: Invalid value: %s (min: %s, max: %s)",
                    value,
                    self._min,
                    self._max,
                )
            return
        if value is not None:
            await super().send_variable(value)
