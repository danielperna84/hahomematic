"""Module for entities implemented actions."""

import logging

from hahomematic.const import DATA_LOAD_SUCCESS, HA_PLATFORM_ACTION
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


class HmAction(GenericEntity):
    """
    Implementation of an action.
    This is an internal default platform that gets automatically generated.
    """

    def __init__(self, device, unique_id, address, parameter, parameter_data):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            parameter=parameter,
            parameter_data=parameter_data,
            platform=HA_PLATFORM_ACTION,
        )

    @property
    def state(self):
        return None

    async def load_data(self) -> int:
        """Load data is not necessary."""
        return DATA_LOAD_SUCCESS

    def add_to_collections(self) -> None:
        """Add entity to central collections."""
        self._device.add_hm_entity(self)
