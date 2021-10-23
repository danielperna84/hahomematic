"""
Module for entities implemented using the
switch platform (https://www.home-assistant.io/integrations/switch/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SWITCH, OPERATION_READ, TYPE_ACTION
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class HM_Switch(GenericEntity):
    """
    Implementation of a switch.
    This is a default platform that gets automatically generated.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self, server, interface_id, unique_id, address, parameter, parameter_data
    ):
        super().__init__(
            server,
            interface_id,
            unique_id,
            address,
            parameter,
            parameter_data,
            HA_PLATFORM_SWITCH,
        )

    @property
    def STATE(self):
        if self.type == TYPE_ACTION:
            return False
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "switch: Failed to get state for %s, %s, %s: %s",
                self.device_type,
                self.address,
                self.parameter,
                err,
            )
            return None
        return self._state

    @STATE.setter
    def STATE(self, value):
        try:
            if self.type == TYPE_ACTION:
                self.proxy.setValue(self.address, self.parameter, True)
            else:
                self.proxy.setValue(self.address, self.parameter, value)
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "switch: Failed to set state for: %s, %s, %s, %s",
                self.device_type,
                self.address,
                self.parameter,
                value,
            )
