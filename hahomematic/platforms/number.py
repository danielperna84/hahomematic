"""
Module for entities implemented using the
number platform (https://www.home-assistant.io/integrations/number/).
"""

import logging

from hahomematic.const import ATTR_HM_VALUE, HA_PLATFORM_NUMBER, OPERATION_READ
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class HM_Number(GenericEntity):
    """
    Implementation of a number.
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
            HA_PLATFORM_NUMBER,
        )

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "number: Failed to get state for %s, %s, %s: %s",
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
            # pylint: disable=no-else-return
            # if value >= self.min and value <= self.max:
            if self.min <= value <= self.max:
                self.proxy.setValue(self.address, self.parameter, value)
                return
            elif self.special:
                if [sv for sv in self.special if value == sv[ATTR_HM_VALUE]]:
                    self.proxy.setValue(self.address, self.parameter, value)
                    return
            LOG.error(
                "number: Invalid value: %s (min: %s, max: %s, special: %s)",
                value,
                self.min,
                self.max,
                self.special,
            )
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "number: Failed to set state for %s, %s, %s, %s",
                self.device_type,
                self.address,
                self.parameter,
                value,
            )
