"""Code to create the required entities for switch entities."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_STATE,
    FIELD_STATE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity

ATTR_CHANNEL_STATE = "channel_state"

_LOGGER = logging.getLogger(__name__)


class HmSwitch(CustomEntity):
    """Class for homematic switch entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        address: str,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[str, Any],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.SWITCH,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "BaseHmSwitch.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _state(self) -> bool | None:
        """Return the temperature of the device."""
        return self._get_entity_state(FIELD_STATE)

    @property
    def _channel_state(self) -> bool | None:
        """Return the temperature of the device."""
        return self._get_entity_state(FIELD_CHANNEL_STATE)

    @property
    def state(self) -> bool | None:
        """Return the current state of the switch."""
        return self._state

    async def set_state(self, value: bool | None) -> None:
        """Set the state of the switch."""
        await self._send_value(FIELD_STATE, value)

    async def turn_on(self) -> None:
        """Turn the switch on."""
        await self._send_value(FIELD_STATE, True)

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self._send_value(FIELD_STATE, False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch."""
        state_attr = super().extra_state_attributes
        if self._channel_state and self._channel_state != self._state:
            state_attr[ATTR_CHANNEL_STATE] = self._channel_state
        return state_attr


def make_ip_switch(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip switch entities."""
    return make_custom_entity(
        device,
        address,
        HmSwitch,
        EntityDefinition.IP_LIGHT_SWITCH,
        group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-FSM*": (make_ip_switch, [1]),
    "HmIP-FSI*": (make_ip_switch, [2]),
    "HmIP-PS*": (make_ip_switch, [2]),
    "HmIP-BSL": (make_ip_switch, [3]),
    "HmIP-DRSI1": (make_ip_switch, [2]),
    "HmIP-DRSI4": (make_ip_switch, [5, 9, 13, 17]),
    "HmIPW-DRS*": (make_ip_switch, [1, 5, 9, 13, 17, 21, 25, 29]),
    "HmIP-MOD-OC8": (make_ip_switch, [9, 13, 17, 21, 25, 29, 33, 37]),
    "HmIP-PCBS": (make_ip_switch, [2]),
    "HmIP-PCBS2": (make_ip_switch, [3, 7]),
    "HmIP-PCBS-BAT": (make_ip_switch, [2]),
    "HmIP-USBSM": (make_ip_switch, [2]),
    # HmIP-MIO16-PCB : Don't add it. Too much functionality. Device is better supported without custom entities.
    # HmIP-MIOB : Don't add it. Too much functionality. Device is better supported without custom entities.
}
