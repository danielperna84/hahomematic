# pylint: disable=line-too-long
"""
Code to create the required entities for cover devices.
"""
from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_COVER
from hahomematic.devices.device_description import (
    DD_PHY_CHANNEL,
    DD_VIRT_CHANNEL,
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_STOP,
    Devices,
    get_device_entities,
    get_device_groups,
)
from hahomematic.entity import CustomEntity
from hahomematic.helpers import generate_unique_id

ATTR_CHANNEL_COVER_LEVEL = "channel_cover_level"
ATTR_CHANNEL_TILT_LEVEL = "channel_tilt_level"
HM_OPEN = 1
HM_CLOSED = 0

_LOGGER = logging.getLogger(__name__)


class HmCover(CustomEntity):

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
        """return the level of the cover"""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """return the channel level state of the cover"""
        return self._get_entity_value(FIELD_CHANNEL_LEVEL)

    @property
    def current_cover_position(self) -> int | None:
        """
        Return current position of cover.
        HA:  0 means closed and 100 is fully open
        """
        if self._level is not None:
            return int(self._level * 100)
        return None

    async def async_set_cover_position(self, position) -> None:
        """Move the cover to a specific position."""
        # Hm cover is closed:1 -> open:0
        position = min(100, max(0, position))
        level = position / 100.0
        await self._send_value(FIELD_LEVEL, level)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._level is not None:
            return self._level == HM_OPEN
        return None

    async def async_open_cover(self) -> None:
        """Open the cover."""
        await self._send_value(FIELD_LEVEL, HM_OPEN)

    async def async_close_cover(self) -> None:
        """Close the cover."""
        await self._send_value(FIELD_LEVEL, HM_CLOSED)

    async def async_stop_cover(self) -> None:
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
    @property
    def _level_2(self) -> float:
        """return the level of the tilt"""
        return self._get_entity_value(FIELD_LEVEL_2)

    @property
    def _channel_level_2(self) -> float:
        """return the channel level of the tilt"""
        return self._get_entity_value(FIELD_CHANNEL_LEVEL_2)

    @property
    def current_cover_tilt_position(self) -> int | None:
        """
        Return current tilt position of cover.
        HA:  0 means closed and 100 is fully open
        """
        if self._level_2 is not None:
            return int(self._level_2 * 100)
        return None

    async def async_set_cover_tilt_position(self, position) -> None:
        """Move the cover to a specific tilt position."""

        position = min(100, max(0, position))
        level = position / 100.0
        await self._send_value(FIELD_LEVEL_2, level)

    async def async_open_cover_tilt(
        self,
    ) -> None:
        """Open the tilt."""
        await self._send_value(FIELD_LEVEL_2, HM_OPEN)

    async def async_close_cover_tilt(self) -> None:
        """Close the tilt."""
        await self._send_value(FIELD_LEVEL_2, HM_CLOSED)

    async def async_stop_cover_tilt(self) -> None:
        """Stop the device if in motion."""
        await self._send_value(FIELD_STOP, True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the cover."""
        state_attr = super().extra_state_attributes
        if self._channel_level_2 and self._channel_level_2 != self._level_2:
            state_attr[ATTR_CHANNEL_TILT_LEVEL] = self._channel_level_2 * 100
        return state_attr


def _make_cover(device, address, cover_class, device_def: Devices):
    """
    Helper to create light entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities = []
    entity_desc = get_device_entities(device_def)
    for device_desc in get_device_groups(device_def):
        channels = device_desc[DD_PHY_CHANNEL]
        # check if virtual channels should be used
        if device.server.enable_virtual_channels:
            channels += device_desc[DD_VIRT_CHANNEL]
        for channel_no in channels:
            unique_id = generate_unique_id(f"{address}:{channel_no}")
            if unique_id in device.server.hm_entities:
                _LOGGER.debug("_make_cover: Skipping %s (already exists)", unique_id)
                continue
            entity = cover_class(
                device=device,
                address=address,
                unique_id=unique_id,
                device_desc=device_desc,
                entity_desc=entity_desc,
                channel_no=channel_no,
            )
            if len(entity.data_entities) > 0:
                entity.add_to_collections()
                entities.append(entity)
    return entities


def make_ip_cover(device, address):
    """Helper to create homematic ip cover entities."""
    return _make_cover(device, address, HmCover, Devices.IP_COVER)


def make_ip_multi_cover(device, address):
    """Helper to create homematic ip cover entities."""
    return _make_cover(device, address, HmCover, Devices.IP_COVER)


def make_ip_wired_multi_cover(device, address):
    """Helper to create homematic ip cover entities."""
    return _make_cover(device, address, HmCover, Devices.IP_COVER)


def make_rf_cover(device, address):
    """Helper to create homematic classic cover entities."""
    return _make_cover(device, address, HmCover, Devices.RF_COVER)


def make_ip_blind(device, address):
    """Helper to create homematic ip cover entities."""
    return _make_cover(device, address, HmBlind, Devices.IP_COVER)


def make_rf_blind(device, address):
    """Helper to create homematic classic cover entities."""
    return _make_cover(device, address, HmBlind, Devices.RF_COVER)


DEVICES = {
    "HmIP-BROLL": make_ip_cover,
    "HmIP-FROLL": make_ip_cover,
    "HmIP-BBL": make_ip_blind,
    "HmIP-FBL": make_ip_blind,
    "HmIP-DRBLI4": make_ip_multi_cover,
    "HM-LC-Bl1*": make_rf_blind,
    "HM-LC-Ja1PBU-FM": make_rf_blind,
    "ZEL STG RM FEP 230V": make_rf_blind,
    "263 146": make_rf_blind,
    "263 147": make_rf_blind,
    "HM-LC-BlX": make_rf_blind,
    "HM-Sec-Win": make_rf_blind,
}
