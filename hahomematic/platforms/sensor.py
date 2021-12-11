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
        address: str,
        parameter: str,
        parameter_data: dict[str, Any],
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HmPlatform.SENSOR,
        )

    @property
    def state(self) -> Any | None:
        """Return the state."""
        if self._state is not None and self._value_list is not None:
            return self._value_list[self._state]

        return self._state
