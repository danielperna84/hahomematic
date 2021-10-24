"""
Module for entities implemented using the
select platform (https://www.home-assistant.io/integrations/select/).
"""

import logging

from hahomematic.const import HA_PLATFORM_SELECT, OPERATION_READ
from hahomematic.entity import GenericEntity

LOG = logging.getLogger(__name__)

# pylint: disable=invalid-name
class HM_Select(GenericEntity):
    """
    Implementation of a select.
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
            HA_PLATFORM_SELECT,
        )

    @property
    def STATE(self):
        try:
            if self._state is None and self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.info(
                "select: Failed to get state for %s, %s, %s: %s",
                self.device_type,
                self.address,
                self.parameter,
                err,
            )
            return None
        return self.value_list[self._state]

    @STATE.setter
    def STATE(self, value):
        try:
            # We allow setting the value via index as well, just in case.
            if isinstance(value, int):
                self.proxy.setValue(self.address, self.parameter, value)
            else:
                self.proxy.setValue(
                    self.address, self.parameter, self.value_list.index(value)
                )
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "select: Failed to set state for: %s, %s, %s, %s",
                self.device_type,
                self.address,
                self.parameter,
                value,
            )
