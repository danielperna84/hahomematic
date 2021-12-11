"""Module for entities implemented actions."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import DATA_LOAD_SUCCESS, HmPlatform
import hahomematic.device as hm_device
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmAction(GenericEntity[None]):
    """
    Implementation of an action.
    This is an internal default platform that gets automatically generated.
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
            platform=HmPlatform.ACTION,
        )

    @property
    def state(self) -> None:
        """Return the state."""
        return None

    async def load_data(self) -> int:
        """Load data is not necessary."""
        return DATA_LOAD_SUCCESS

    def add_to_collections(self) -> None:
        """Add entity to central collections."""
        self._device.add_hm_entity(self)
