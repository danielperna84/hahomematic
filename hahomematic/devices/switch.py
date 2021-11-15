# pylint: disable=line-too-long
"""
Code to create the required entities for switch entities.
"""

import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_SWITCH
from hahomematic.devices.device_description import (
    FIELD_CHANNEL_STATE,
    FIELD_STATE,
    Devices,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

ATTR_CHANNEL_STATE = "channel_state"

_LOGGER = logging.getLogger(__name__)


class HmSwitch(CustomEntity):

    # pylint: disable=too-many-arguments
    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_SWITCH,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "BaseHmSwitch.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _state(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_STATE)

    @property
    def _channel_state(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_CHANNEL_STATE)

    @property
    def state(self):
        """Return the current state of the switch."""
        return self._state

    async def set_state(self, value):
        """Set the state of the switch"""
        await self._send_value(FIELD_STATE, value)

    async def async_turn_on(self) -> None:
        """Turn the switch on."""
        await self._send_value(FIELD_STATE, True)

    async def async_turn_off(self) -> None:
        """Turn the switch off."""
        await self._send_value(FIELD_STATE, False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch."""
        state_attr = super().extra_state_attributes
        if self._channel_state and self._channel_state != self._state:
            state_attr[ATTR_CHANNEL_STATE] = self._channel_state
        return state_attr


def make_ip_switch(device, address):
    """Helper to create homematic ip switch entities."""
    return make_custom_entity(device, address, HmSwitch, Devices.IP_SWITCH)


def make_ip_switch_bsl(device, address):
    """Helper to create homematic ip switch entities."""
    return make_custom_entity(device, address, HmSwitch, Devices.IP_SWITCH_BSL)


def make_ip_plug_switch(device, address):
    """Helper to create homematic ip switch entities."""
    return make_custom_entity(device, address, HmSwitch, Devices.IP_PLUG_SWITCH)


def make_ip_multi_switch(device, address):
    """Helper to create homematic ip multi switch entities."""
    return make_custom_entity(device, address, HmSwitch, Devices.IP_MULTI_SWITCH)


def make_ip_wired_multi_switch(device, address):
    """Helper to create homematic ip multi switch entities."""
    return make_custom_entity(device, address, HmSwitch, Devices.IP_WIRED_MULTI_SWITCH)


DEVICES = {
    "HmIP-FSM": make_ip_switch,
    "HmIP-PS*": make_ip_plug_switch,
    "HmIP-BSL": make_ip_switch_bsl,
    "HmIP-DRSI4": make_ip_multi_switch,
    "HmIPW-DRS*": make_ip_wired_multi_switch,
}
