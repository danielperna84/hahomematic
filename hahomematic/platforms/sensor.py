"""
Module for entities implemented using the
sensor platform (https://www.home-assistant.io/integrations/sensor/).
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmSensor(GenericEntity[Any]):
    """
    Implementation of a sensor.
    This is a default platform that gets automatically generated.
    """

    def __init__(
        self,
        device: hm_device.HmDevice,
        unique_id: str,
        channel_address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            channel_address=channel_address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.SENSOR,
        )

    @property
    def value(self) -> Any | None:
        """Return the value."""
        if self._value is not None and self._value_list is not None:
            return self._value_list[self._value]
        return self._value
