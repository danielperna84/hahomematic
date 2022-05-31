"""
Module for entities implemented using the
switch platform (https://www.home-assistant.io/integrations/switch/).
"""
from __future__ import annotations

import logging
from typing import Any, cast

import hahomematic.central_unit as hm_central
from hahomematic.const import HM_ARG_ON_TIME, TYPE_ACTION, HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, GenericSystemVariable
from hahomematic.helpers import SystemVariableData

PARAM_ON_TIME = "ON_TIME"
_LOGGER = logging.getLogger(__name__)


class HmSwitch(GenericEntity[bool]):
    """
    Implementation of a switch.
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
            platform=HmPlatform.SWITCH,
        )

    @property
    def value(self) -> bool | None:
        """Get the value of the entity."""
        if self._type == TYPE_ACTION:
            return False
        return self._value

    async def turn_on(self, **kwargs: dict[str, Any] | None) -> None:
        """Turn the switch on."""
        if HM_ARG_ON_TIME in kwargs:
            on_time = float(cast(float, kwargs[HM_ARG_ON_TIME]))
            await self.set_on_time_value(on_time=on_time)
        await self.send_value(True)

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self.send_value(False)

    async def set_on_time_value(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        await self._client.set_value_by_paramset_key(
            channel_address=self.channel_address,
            paramset_key=self._paramset_key,
            parameter=PARAM_ON_TIME,
            value=float(on_time),
        )


class HmSysvarSwitch(GenericSystemVariable):
    """
    Implementation of a sysvar switch entity.
    """

    def __init__(self, central: hm_central.CentralUnit, data: SystemVariableData):
        """Initialize the entity."""
        super().__init__(central=central, data=data, platform=HmPlatform.HUB_SWITCH)
