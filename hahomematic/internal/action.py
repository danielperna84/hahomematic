"""
Module for entities implemented actionx.
"""

import logging

from hahomematic.const import ATTR_HM_VALUE, DATA_LOAD_SUCCESS, HA_PLATFORM_ACTION
from hahomematic.entity import GenericEntity

_LOGGER = logging.getLogger(__name__)


# pylint: disable=invalid-name
class HmAction(GenericEntity):
    """
    Implementation of an action.
    This is an internal default platform that gets automatically generated.
    """

    # pylint: disable=too-many-arguments
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
        """load data is not necessary."""
        return DATA_LOAD_SUCCESS

    def add_to_collections(self) -> None:
        """add entity to server collections"""
        self._device.add_hm_entity(self)
