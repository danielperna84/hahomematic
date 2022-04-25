"""Code to create the required entities for switch entities."""
from __future__ import annotations

import logging
from typing import Any, cast

from hahomematic.const import HM_ARG_ON_TIME, HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_STATE,
    FIELD_ON_TIME_VALUE,
    FIELD_STATE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.switch import HmSwitch

_LOGGER = logging.getLogger(__name__)

# HM constants
ATTR_CHANNEL_STATE = "channel_state"


class CeSwitch(CustomEntity):
    """Class for homematic switch entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        device_address: str,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int, set[str]],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            device_address=device_address,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.SWITCH,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "BaseHmSwitch.__init__(%s, %s, %s)",
            self._device.interface_id,
            device_address,
            unique_id,
        )

    @property
    def _e_state(self) -> HmSwitch:
        """Return the state entity of the device."""
        return self._get_entity(field_name=FIELD_STATE, entity_type=HmSwitch)

    @property
    def _e_on_time_value(self) -> HmAction:
        """Return the on_time entity of the device."""
        return self._get_entity(field_name=FIELD_ON_TIME_VALUE, entity_type=HmAction)

    @property
    def _channel_state(self) -> bool | None:
        """Return the temperature of the device."""
        return self._get_entity_value(field_name=FIELD_CHANNEL_STATE)

    @property
    def value(self) -> bool | None:
        """Return the current value of the switch."""
        return self._e_state.value

    async def turn_on(self, **kwargs: dict[str, Any] | None) -> None:
        """Turn the switch on."""
        if HM_ARG_ON_TIME in kwargs and isinstance(self._e_on_time_value, HmAction):
            on_time: float = float(cast(float, kwargs[HM_ARG_ON_TIME]))
            await self._e_on_time_value.send_value(on_time)

        await self._e_state.turn_on()

    async def turn_off(self) -> None:
        """Turn the switch off."""
        await self._e_state.turn_off()

    async def set_on_time_value(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        await self._e_on_time_value.send_value(float(on_time))

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the switch."""
        state_attr = super().attributes
        if self._channel_state and self._channel_state != self._e_state.value:
            state_attr[ATTR_CHANNEL_STATE] = self._channel_state
        return state_attr


def make_ip_switch(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip switch entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeSwitch,
        device_enum=EntityDefinition.IP_SWITCH,
        group_base_channels=group_base_channels,
    )


def make_rf_switch(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip switch entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeSwitch,
        device_enum=EntityDefinition.RF_SWITCH,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-BSM": (make_ip_switch, [3]),
    "HmIP-FSM": (make_ip_switch, [1]),
    "HmIP-FSI": (make_ip_switch, [2]),
    "HmIP-PS": (make_ip_switch, [2]),
    "HmIP-BSL": (make_ip_switch, [3]),
    "HmIP-DRSI1": (make_ip_switch, [2]),
    "HmIP-DRSI4": (make_ip_switch, [5, 9, 13, 17]),
    "HmIPW-DRS": (make_ip_switch, [1, 5, 9, 13, 17, 21, 25, 29]),
    "HmIP-MOD-OC8": (make_ip_switch, [9, 13, 17, 21, 25, 29, 33, 37]),
    "HmIP-PCBS": (make_ip_switch, [2]),
    "HmIP-PCBS2": (make_ip_switch, [3, 7]),
    "HmIP-PCBS-BAT": (make_ip_switch, [2]),
    "HmIP-SCTH230": (make_ip_switch, [7]),
    "HmIP-USBSM": (make_ip_switch, [2]),
    "HmIP-WGC": (make_ip_switch, [2]),
    "HmIP-WHS2": (make_ip_switch, [1, 5]),
    "HmIPW-FIO6": (make_ip_switch, [7, 11, 15, 19, 23, 27]),
    # "HM-LC-Sw": (make_rf_switch, [1, 2, 3, 4]),
    # "HM-ES-PM": (make_rf_switch, [1]),
}

# HmIP-MIO16-PCB : Don't add it. Too much functionality. Device is better supported without custom entities.
# HmIP-MIOB : Don't add it. Too much functionality. Device is better supported without custom entities.

BLACKLISTED_DEVICES: list[str] = []
