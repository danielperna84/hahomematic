"""Code to create the required entities for cover devices."""

from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_DOOR_COMMAND,
    FIELD_DOOR_STATE,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_STOP,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity

ATTR_CHANNEL_COVER_LEVEL = "channel_cover_level"
ATTR_CHANNEL_TILT_LEVEL = "channel_tilt_level"
# must be float!
HM_OPEN = 1.0
# must be float!
HM_CLOSED = 0.0

GARAGE_DOOR_COMMAND_NOP = 0
GARAGE_DOOR_COMMAND_OPEN = 1
GARAGE_DOOR_COMMAND_STOP = 2
GARAGE_DOOR_COMMAND_CLOSE = 3
GARAGE_DOOR_COMMAND_PARTIAL_OPEN = 4

GARAGE_DOOR_STATE_CLOSED = 0
GARAGE_DOOR_STATE_OPEN = 1
GARAGE_DOOR_STATE_VENTILATION_POSITION = 2
GARAGE_DOOR_STATE_POSITION_UNKNOWN = 3

_LOGGER = logging.getLogger(__name__)


class HmCover(CustomEntity):
    """Class for homematic cover entities."""

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
            platform=HmPlatform.COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _level(self) -> float | None:
        """Return the level of the cover."""
        return self._get_entity_state(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float | None:
        """Return the channel level state of the cover."""
        channel_level = self._get_entity_state(FIELD_CHANNEL_LEVEL)
        if channel_level:
            return float(channel_level)
        return self._level

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._channel_level is not None:
            return int(self._channel_level * 100)
        return None

    async def set_cover_position(self, position: float) -> None:
        """Move the cover to a specific position."""
        # Hm cover is closed:1 -> open:0
        position = min(100.0, max(0.0, position))
        level = position / 100.0
        await self._send_value(FIELD_LEVEL, level)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._channel_level is not None:
            return self._channel_level == HM_OPEN
        return None

    async def open_cover(self) -> None:
        """Open the cover."""
        await self._send_value(FIELD_LEVEL, HM_OPEN)

    async def close_cover(self) -> None:
        """Close the cover."""
        await self._send_value(FIELD_LEVEL, HM_CLOSED)

    async def stop_cover(self) -> None:
        """Stop the device if in motion."""
        await self._send_value(FIELD_STOP, True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the cover."""
        state_attr = super().extra_state_attributes
        if self._channel_level and self._channel_level != self._level:
            state_attr[ATTR_CHANNEL_COVER_LEVEL] = self._channel_level * 100
        return state_attr


class HmBlind(HmCover):
    """Class for homematic blind entities."""

    @property
    def _level_2(self) -> float | None:
        """Return the level of the tilt."""
        return self._get_entity_state(FIELD_LEVEL_2)

    @property
    def _channel_level_2(self) -> float | None:
        """Return the channel level of the tilt."""
        channel_level_2 = self._get_entity_state(FIELD_CHANNEL_LEVEL_2)
        if channel_level_2:
            return float(channel_level_2)
        return self._level_2

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._channel_level_2 is not None:
            return int(self._channel_level_2 * 100)
        return None

    async def set_cover_tilt_position(self, position: float) -> None:
        """Move the cover to a specific tilt position."""
        position = min(100.0, max(0.0, position))
        level = position / 100.0
        await self._send_value(FIELD_LEVEL_2, level)

    async def open_cover_tilt(self) -> None:
        """Open the tilt."""
        await self._send_value(FIELD_LEVEL_2, HM_OPEN)

    async def close_cover_tilt(self) -> None:
        """Close the tilt."""
        await self._send_value(FIELD_LEVEL_2, HM_CLOSED)

    async def stop_cover_tilt(self) -> None:
        """Stop the device if in motion."""
        await self._send_value(FIELD_STOP, True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the cover."""
        state_attr = super().extra_state_attributes
        if self._channel_level_2 and self._channel_level_2 != self._level_2:
            state_attr[ATTR_CHANNEL_TILT_LEVEL] = self._channel_level_2 * 100
        return state_attr


class HmGarage(CustomEntity):
    """Class for homematic garage entities."""

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
            platform=HmPlatform.COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmGarage.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _door_state(self) -> int | None:
        """Return the state of the garage door."""
        return self._get_entity_state(FIELD_DOOR_STATE)

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._door_state == GARAGE_DOOR_STATE_OPEN:
            return 100
        if self._door_state == GARAGE_DOOR_STATE_VENTILATION_POSITION:
            return 10
        if self._door_state == GARAGE_DOOR_STATE_CLOSED:
            return 0
        return None

    async def set_cover_position(self, position: float) -> None:
        """Move the garage door to a specific position."""
        if 50.0 < position <= 100.0:
            await self.open_cover()
        elif 10.0 < position <= 50.0:
            await self.vent_cover()
        elif 0.0 <= position <= 10.0:
            await self.close_cover()

    @property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._door_state is not None:
            return self._door_state == GARAGE_DOOR_STATE_CLOSED
        return None

    async def open_cover(self) -> None:
        """Open the garage door."""
        await self._send_value(FIELD_DOOR_COMMAND, GARAGE_DOOR_COMMAND_OPEN)

    async def close_cover(self) -> None:
        """Close the garage door."""
        await self._send_value(FIELD_DOOR_COMMAND, GARAGE_DOOR_COMMAND_CLOSE)

    async def stop_cover(self) -> None:
        """Stop the device if in motion."""
        await self._send_value(FIELD_DOOR_COMMAND, GARAGE_DOOR_COMMAND_STOP)

    async def vent_cover(self) -> None:
        """Move the garage door to vent position."""
        await self._send_value(FIELD_DOOR_COMMAND, GARAGE_DOOR_COMMAND_PARTIAL_OPEN)


def make_ip_cover(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device, address, HmCover, EntityDefinition.IP_COVER, group_base_channels
    )


def make_rf_cover(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device, address, HmCover, EntityDefinition.RF_COVER, group_base_channels
    )


def make_ip_blind(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device, address, HmBlind, EntityDefinition.IP_COVER, group_base_channels
    )


def make_ip_garage(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip garage entities."""
    return make_custom_entity(
        device, address, HmGarage, EntityDefinition.IP_GARAGE, group_base_channels
    )


def make_rf_blind(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device, address, HmBlind, EntityDefinition.RF_COVER, group_base_channels
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-BROLL": (make_ip_cover, [3]),
    "HmIP-FROLL": (make_ip_cover, [3]),
    "HmIP-BBL": (make_ip_blind, [3]),
    "HmIP-FBL": (make_ip_blind, [3]),
    "HmIP-HDM1": (make_ip_blind, [0]),  # 0 is correct, HDM1 has no status channel.
    "HmIP-DRBLI4": (make_ip_blind, [9, 13, 17, 21]),
    "HmIPW-DRBL4": (make_ip_blind, [1, 5, 9, 13]),
    "HmIP-MOD-HO": (make_ip_garage, []),
    "HmIP-MOD-TM": (make_ip_garage, []),
    "HM-LC-Bl1*": (make_rf_blind, []),
    "HM-LC-Ja1PBU-FM": (make_rf_blind, []),
    "ZEL STG RM FEP 230V": (make_rf_blind, []),
    "263 146": (make_rf_blind, []),
    "263 147": (make_rf_blind, []),
    "HM-LC-BlX": (make_rf_blind, []),
    "HM-Sec-Win": (make_rf_blind, []),
    "HMW-LC-Bl1*": (make_rf_blind, []),
}
