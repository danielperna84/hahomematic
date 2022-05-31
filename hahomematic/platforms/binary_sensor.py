"""
Module for entities implemented using the
binary_sensor platform (https://www.home-assistant.io/integrations/binary_sensor/).
"""
from __future__ import annotations

import logging
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity, GenericSystemVariable
from hahomematic.helpers import SystemVariableData

_LOGGER = logging.getLogger(__name__)


class HmBinarySensor(GenericEntity[bool]):
    """
    Implementation of a binary_sensor.
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
            platform=HmPlatform.BINARY_SENSOR,
        )

    @property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._value is not None:
            return self._value
        return self._default


class HmSysvarBinarySensor(GenericSystemVariable):
    """
    Implementation of a sysvar binary_sensor.
    """

    def __init__(self, central: hm_central.CentralUnit, data: SystemVariableData):
        """Initialize the entity."""
        super().__init__(
            central=central, data=data, platform=HmPlatform.HUB_BINARY_SENSOR
        )

    @property
    def value(self) -> bool | None:
        """Return the value of the entity."""
        if self._value is not None:
            return bool(self._value)
        return None
