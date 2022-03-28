"""Code to create the required entities for cover devices."""

from __future__ import annotations

import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_CHANNEL_OPERATION_MODE,
    FIELD_DIRECTION,
    FIELD_DOOR_COMMAND,
    FIELD_DOOR_STATE,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_SECTION,
    FIELD_STOP,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.number import HmFloat

_LOGGER = logging.getLogger(__name__)

# HM constants
ATTR_CHANNEL_COVER_LEVEL = "channel_cover_level"
ATTR_CHANNEL_TILT_LEVEL = "channel_tilt_level"

HM_OPEN: float = 1.0  # must be float!
HM_CLOSED: float = 0.0  # must be float!

HM_OPENING = "UP"
HM_CLOSING = "DOWN"

GARAGE_DOOR_COMMAND_NOP = "NOP"
GARAGE_DOOR_COMMAND_OPEN = "OPEN"
GARAGE_DOOR_COMMAND_STOP = "STOP"
GARAGE_DOOR_COMMAND_CLOSE = "CLOSE"
GARAGE_DOOR_COMMAND_PARTIAL_OPEN = "PARTIAL_OPEN"

GARAGE_DOOR_SECTION_CLOSING = 2
GARAGE_DOOR_SECTION_OPENING = 5

GARAGE_DOOR_STATE_CLOSED = "CLOSED"
GARAGE_DOOR_STATE_OPEN = "OPEN"
GARAGE_DOOR_STATE_VENTILATION_POSITION = "VENTILATION_POSITION"
GARAGE_DOOR_STATE_POSITION_UNKNOWN = "POSITION_UNKNOWN"


class CeCover(CustomEntity):
    """Class for homematic cover entities."""

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
            platform=HmPlatform.COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmCover.__init__(%s, %s, %s)",
            self._device.interface_id,
            device_address,
            unique_id,
        )

    @property
    def _direction(self) -> str | None:
        """Return the channel level of the cover."""
        return self._get_entity_value(field_name=FIELD_DIRECTION)

    @property
    def _e_level(self) -> HmFloat:
        """Return the level entity of the cover."""
        return self._get_entity(field_name=FIELD_LEVEL, entity_type=HmFloat)

    @property
    def _e_stop(self) -> HmAction:
        """Return the stop entity of the cover."""
        return self._get_entity(field_name=FIELD_STOP, entity_type=HmAction)

    @property
    def _e_channel_operation_mode(self) -> HmAction:
        """Return the channel_operation_mode entity of the cover."""
        return self._get_entity(
            field_name=FIELD_CHANNEL_OPERATION_MODE, entity_type=HmAction
        )

    @property
    def _channel_level(self) -> float | None:
        """Return the channel level of the cover."""
        channel_level = self._get_entity_value(field_name=FIELD_CHANNEL_LEVEL)
        if channel_level is not None:
            return float(channel_level)
        return self._e_level.value if self._e_level.value is not None else HM_CLOSED

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        if self._channel_level is not None:
            return int(self._channel_level * 100)
        return None

    @property
    def channel_operation_mode(self) -> str | None:
        """Return channel_operation_mode of cover."""
        if self._e_channel_operation_mode:
            return self._e_channel_operation_mode.value
        return None

    async def set_cover_position(self, position: float) -> None:
        """Move the cover to a specific position."""
        position = min(100.0, max(0.0, position))
        level = position / 100.0
        await self._set_cover_level(level=level)

    async def _set_cover_level(self, level: float) -> None:
        """Move the cover to a specific position. Value range is 0.0 to 1.0."""
        await self._e_level.send_value(level)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._channel_level is not None:
            return self._channel_level == HM_CLOSED
        return None

    @property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._direction is not None:
            return self._direction == HM_OPENING
        return None

    @property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._direction is not None:
            return self._direction == HM_CLOSING
        return None

    async def open_cover(self) -> None:
        """Open the cover."""
        await self._set_cover_level(level=HM_OPEN)

    async def close_cover(self) -> None:
        """Close the cover."""
        await self._set_cover_level(level=HM_CLOSED)

    async def stop_cover(self) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(True)

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the cover."""
        state_attr = super().attributes
        if self._channel_level and self._channel_level != self._e_level.value:
            state_attr[ATTR_CHANNEL_COVER_LEVEL] = self._channel_level * 100
        return state_attr


class CeBlind(CeCover):
    """Class for homematic blind entities."""

    @property
    def _e_level_2(self) -> HmFloat:
        """Return the level entity of the tilt."""
        return self._get_entity(field_name=FIELD_LEVEL_2, entity_type=HmFloat)

    @property
    def _channel_level_2(self) -> float | None:
        """Return the channel level of the tilt."""
        channel_level_2 = self._get_entity_value(field_name=FIELD_CHANNEL_LEVEL_2)
        if channel_level_2 is not None:
            return float(channel_level_2)
        return self._e_level_2.value if self._e_level_2.value is not None else HM_CLOSED

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
        await self._set_cover_tilt_level(level)

    async def _set_cover_tilt_level(self, level: float) -> None:
        """Move the cover to a specific tilt level. Value range is 0.0 to 1.0."""
        await self._e_level_2.send_value(level)

    async def open_cover_tilt(self) -> None:
        """Open the tilt."""
        await self._set_cover_tilt_level(level=HM_OPEN)

    async def close_cover_tilt(self) -> None:
        """Close the tilt."""
        await self._set_cover_tilt_level(level=HM_CLOSED)

    async def stop_cover_tilt(self) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(True)

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the cover."""
        state_attr = super().attributes
        if self._channel_level_2 and self._channel_level_2 != self._e_level_2.value:
            state_attr[ATTR_CHANNEL_TILT_LEVEL] = self._channel_level_2 * 100
        return state_attr


class CeIpBlind(CeBlind):
    """Class for homematic ip blind entities."""

    async def open_cover(self) -> None:
        """Open the cover and open the tilt."""
        await super()._set_cover_tilt_level(level=HM_OPEN)
        await self._set_cover_level(level=HM_OPEN)

    async def close_cover(self) -> None:
        """Close the cover and close the tilt."""
        await super()._set_cover_tilt_level(level=HM_CLOSED)
        await self._set_cover_level(level=HM_CLOSED)

    async def _set_cover_tilt_level(self, level: float) -> None:
        """Move the cover to a specific tilt level. Value range is 0.0 to 1.0."""
        await super()._set_cover_tilt_level(level=level)
        await self.set_cover_position(position=self.current_cover_position or 0)


class CeGarage(CustomEntity):
    """Class for homematic garage entities."""

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
            platform=HmPlatform.COVER,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "HmGarage.__init__(%s, %s, %s)",
            self._device.interface_id,
            device_address,
            unique_id,
        )

    @property
    def _door_state(self) -> str | None:
        """Return the door state entity of the garage door."""
        return self._get_entity_value(field_name=FIELD_DOOR_STATE)

    @property
    def _e_door_command(self) -> HmAction:
        """Return the door_command entity of the cover."""
        return self._get_entity(field_name=FIELD_DOOR_COMMAND, entity_type=HmAction)

    @property
    def _section(self) -> int | None:
        """Return the section entity of the garage door."""
        return self._get_entity_value(field_name=FIELD_SECTION)

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

    @property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._section is not None:
            return self._section == GARAGE_DOOR_SECTION_OPENING
        return None

    @property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._section is not None:
            return self._section == GARAGE_DOOR_SECTION_CLOSING
        return None

    async def open_cover(self) -> None:
        """Open the garage door."""
        await self._e_door_command.send_value(GARAGE_DOOR_COMMAND_OPEN)

    async def close_cover(self) -> None:
        """Close the garage door."""
        await self._e_door_command.send_value(GARAGE_DOOR_COMMAND_CLOSE)

    async def stop_cover(self) -> None:
        """Stop the device if in motion."""
        await self._e_door_command.send_value(GARAGE_DOOR_COMMAND_STOP)

    async def vent_cover(self) -> None:
        """Move the garage door to vent position."""
        await self._e_door_command.send_value(GARAGE_DOOR_COMMAND_PARTIAL_OPEN)


def make_ip_cover(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeCover,
        device_enum=EntityDefinition.IP_COVER,
        group_base_channels=group_base_channels,
    )


def make_rf_cover(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeCover,
        device_enum=EntityDefinition.RF_COVER,
        group_base_channels=group_base_channels,
    )


def make_ip_blind(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip cover entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeIpBlind,
        device_enum=EntityDefinition.IP_COVER,
        group_base_channels=group_base_channels,
    )


def make_ip_garage(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip garage entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeGarage,
        device_enum=EntityDefinition.IP_GARAGE,
        group_base_channels=group_base_channels,
    )


def make_rf_blind(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic cover entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeBlind,
        device_enum=EntityDefinition.RF_COVER,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-BROLL": (make_ip_cover, [3]),
    "HmIP-FROLL": (make_ip_cover, [3]),
    "HmIP-BBL": (make_ip_blind, [3]),
    "HmIP-FBL": (make_ip_blind, [3]),
    "HmIP-HDM": (make_ip_blind, [0]),  # 0 is correct, HDM1 has no status channel.
    "HmIP-DRBLI4": (make_ip_blind, [9, 13, 17, 21]),
    "HmIPW-DRBL4": (make_ip_blind, [1, 5, 9, 13]),
    "HmIP-MOD-HO": (make_ip_garage, [1]),
    "HmIP-MOD-TM": (make_ip_garage, [1]),
    "HM-LC-Bl1-FM-2": (make_rf_cover, [1]),
    "HM-LC-Bl1-FM": (make_rf_cover, [1]),
    "HM-LC-Bl1-PB-FM": (make_rf_cover, [1]),
    "HM-LC-Bl1-SM-2": (make_rf_cover, [1]),
    "HM-LC-Bl1-SM": (make_rf_cover, [1]),
    "HM-LC-Bl1PBU-FM": (make_rf_cover, [1]),
    "HM-LC-JaX": (make_rf_blind, [1]),
    "HM-LC-Ja1PBU-FM": (make_rf_blind, [1]),
    "ZEL STG RM FEP 230V": (make_rf_blind, [1]),
    "263 146": (make_rf_blind, [1]),
    "263 147": (make_rf_blind, [1]),
    "HM-LC-BlX": (make_rf_blind, [1]),
    "HM-Sec-Win": (make_rf_blind, [1]),
    "HMW-LC-Bl1": (make_rf_blind, [3]),
}

BLACKLISTED_DEVICES: list[str] = []
