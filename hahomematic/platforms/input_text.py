"""
Module for entities implemented using the
input_text platform (https://www.home-assistant.io/integrations/input_text/).
"""

import logging

from hahomematic.const import HA_PLATFORM_INPUT_TEXT, OPERATION_READ
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class HM_Input_Text(GenericEntity):
    """
    Implementation of a input_text.
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
            HA_PLATFORM_INPUT_TEXT,
        )

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "input_text: Failed to get state for %s, %s, %s: %s",
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
            self.proxy.setValue(self.address, self.parameter, str(value))
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "input_text: Failed to set state for: %s, %s, %s, %s",
                self.device_type,
                self.address,
                self.parameter,
                value,
            )
