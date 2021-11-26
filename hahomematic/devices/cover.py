"""Code to create the required entities for cover devices."""

from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_COVER
from hahomematic.devices.device_description import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_STOP,
    Devices,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

ATTR_CHANNEL_COVER_LEVEL = "channel_cover_level"
ATTR_CHANNEL_TILT_LEVEL = "channel_tilt_level"
HM_OPEN = 1.0
HM_CLOSED = 0.0

_LOGGER = logging.getLogger(__name__)


class HmCover(CustomEntity):
    """Class for homematic cover entities."""

    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _level(self) -> float:
        """Return the level of the cover."""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """Return the channel level state of the cover."""
        channel_level = self._get_entity_value(FIELD_CHANNEL_LEVEL)
        if channel_level:
            return channel_level
        return self._level

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._channel_level is not None:
            return int(self._channel_level * 100)
        return None

    async def set_cover_position(self, position) -> None:
        """Move the cover to a specific position."""
        # Hm cover is closed:1 -> open:0
        position = min(100, max(0, position))
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
    def _level_2(self) -> float:
        """Return the level of the tilt."""
        return self._get_entity_value(FIELD_LEVEL_2)

    @property
    def _channel_level_2(self) -> float:
        """Return the channel level of the tilt."""
        channel_level_2 = self._get_entity_value(FIELD_CHANNEL_LEVEL_2)
        if channel_level_2:
            return channel_level_2
        return self._level_2

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        if self._channel_level_2 is not None:
            return int(self._channel_level_2 * 100)
        return None

    async def set_cover_tilt_position(self, position) -> None:
        """Move the cover to a specific tilt position."""
        position = min(100, max(0, position))
        level = position / 100.0
        await self._send_value(FIELD_LEVEL_2, level)

    async def open_cover_tilt(
        self,
    ) -> None:
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


def make_ip_cover(device, address, group_base_channels: [int]):
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device, address, HmCover, Devices.IP_COVER, group_base_channels
    )


def make_rf_cover(device, address, group_base_channels: [int]):
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device, address, HmCover, Devices.RF_COVER, group_base_channels
    )


def make_ip_blind(device, address, group_base_channels: [int]):
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device, address, HmBlind, Devices.IP_COVER, group_base_channels
    )


def make_rf_blind(device, address, group_base_channels: [int]):
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device, address, HmBlind, Devices.RF_COVER, group_base_channels
    )


DEVICES = {
    "HmIP-BROLL": (make_ip_cover, [3]),
    "HmIP-FROLL": (make_ip_cover, [3]),
    "HmIP-BBL": (make_ip_blind, [3]),
    "HmIP-FBL": (make_ip_blind, [3]),
    "HmIP-HDM1": (make_ip_blind, [0]),
    "HmIP-DRBLI4": (make_ip_cover, [9, 13, 17, 21]),
    "HmIPW-DRBL4": (make_ip_cover, [1, 5, 9, 13]),
    "HM-LC-Bl1*": (make_rf_blind, []),
    "HM-LC-Ja1PBU-FM": (make_rf_blind, []),
    "ZEL STG RM FEP 230V": (make_rf_blind, []),
    "263 146": (make_rf_blind, []),
    "263 147": (make_rf_blind, []),
    "HM-LC-BlX": (make_rf_blind, []),
    "HM-Sec-Win": (make_rf_blind, []),
}
