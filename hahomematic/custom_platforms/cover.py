"""Code to create the required entities for cover devices."""

from __future__ import annotations

from hahomematic.const import HmEntityUsage, HmPlatform
from hahomematic.custom_platforms.entity_definition import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_DIRECTION,
    FIELD_DOOR_COMMAND,
    FIELD_DOOR_STATE,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_SECTION,
    FIELD_STOP,
    CustomConfig,
    EntityDefinition,
    ExtendedConfig,
    make_custom_entity,
)
from hahomematic.decorators import value_property
import hahomematic.device as hmd
import hahomematic.entity as hme
from hahomematic.entity import CustomEntity
from hahomematic.generic_platforms.action import HmAction
from hahomematic.generic_platforms.number import HmFloat
from hahomematic.generic_platforms.sensor import HmSensor

HM_OPEN: float = 1.0  # must be float!
HM_CLOSED: float = 0.0  # must be float!
HM_WD_CLOSED: float = -0.005  # must be float! HM-Sec-Win

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
    """Class for HomeMatic cover entities."""

    _attr_platform = HmPlatform.COVER
    _attr_hm_closed_state: float = HM_CLOSED
    _attr_hm_open_state: float = HM_OPEN

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_direction: HmSensor = self._get_entity(
            field_name=FIELD_DIRECTION, entity_type=HmSensor
        )
        self._e_level: HmFloat = self._get_entity(field_name=FIELD_LEVEL, entity_type=HmFloat)
        self._e_stop: HmAction = self._get_entity(field_name=FIELD_STOP, entity_type=HmAction)
        self._e_channel_level: HmSensor = self._get_entity(
            field_name=FIELD_CHANNEL_LEVEL, entity_type=HmSensor
        )

    @property
    def channel_level(self) -> float:
        """Return the channel level of the cover."""
        if self._e_channel_level.value is not None and self.usage == HmEntityUsage.CE_PRIMARY:
            return float(self._e_channel_level.value)
        return (
            self._e_level.value if self._e_level.value is not None else self._attr_hm_closed_state
        )

    @value_property
    def current_cover_position(self) -> int:
        """Return current position of cover."""
        return int(self.channel_level * 100)

    @value_property
    def channel_operation_mode(self) -> str | None:
        """Return channel_operation_mode of cover."""
        if self._e_channel_level.value is not None:
            return self._e_channel_level.channel_operation_mode
        return None

    async def set_cover_position(self, position: float) -> None:
        """Move the cover to a specific position."""
        position = min(100.0, max(0.0, position))
        level = position / 100.0
        await self._set_cover_level(level=level)

    async def _set_cover_level(self, level: float) -> None:
        """Move the cover to a specific position. Value range is 0.0 to 1.0."""
        await self._e_level.send_value(level)

    @value_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self.channel_level == self._attr_hm_closed_state

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == HM_CLOSING
        return None

    async def open_cover(self) -> None:
        """Open the cover."""
        await self._set_cover_level(level=self._attr_hm_open_state)

    async def close_cover(self) -> None:
        """Close the cover."""
        await self._set_cover_level(level=self._attr_hm_closed_state)

    async def stop_cover(self) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(True)


class CeWindowDrive(CeCover):
    """Class for Homematic window drive."""

    _attr_hm_closed_state: float = HM_WD_CLOSED
    _attr_hm_open_state: float = HM_OPEN

    async def _set_cover_level(self, level: float) -> None:
        """Move the window drive to a specific position. Value range is -0.005 to 1.0."""
        if level == 0.0:
            wd_level = HM_WD_CLOSED
        elif 0.0 < level <= 0.01:
            wd_level = 0
        else:
            wd_level = level
        await self._e_level.send_value(value=wd_level, do_validate=False)


class CeBlind(CeCover):
    """Class for HomeMatic blind entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_level_2: HmFloat = self._get_entity(field_name=FIELD_LEVEL_2, entity_type=HmFloat)
        self._e_channel_level_2: HmSensor = self._get_entity(
            field_name=FIELD_CHANNEL_LEVEL_2, entity_type=HmSensor
        )

    @property
    def channel_tilt_level(self) -> float:
        """Return the channel level of the tilt."""
        if self._e_channel_level_2.value is not None and self.usage == HmEntityUsage.CE_PRIMARY:
            return float(self._e_channel_level_2.value)
        return (
            self._e_level_2.value
            if self._e_level_2.value is not None
            else self._attr_hm_closed_state
        )

    @value_property
    def current_cover_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return int(self.channel_tilt_level * 100)

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
        await self._set_cover_tilt_level(level=self._attr_hm_open_state)

    async def close_cover_tilt(self) -> None:
        """Close the tilt."""
        await self._set_cover_tilt_level(level=self._attr_hm_closed_state)

    async def stop_cover_tilt(self) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(True)


class CeIpBlind(CeBlind):
    """Class for HomematicIP blind entities."""

    async def open_cover(self) -> None:
        """Open the cover and open the tilt."""
        await super()._set_cover_tilt_level(level=self._attr_hm_open_state)
        await self._set_cover_level(level=self._attr_hm_open_state)

    async def close_cover(self) -> None:
        """Close the cover and close the tilt."""
        await super()._set_cover_tilt_level(level=self._attr_hm_closed_state)
        await self._set_cover_level(level=self._attr_hm_closed_state)

    async def _set_cover_tilt_level(self, level: float) -> None:
        """Move the cover to a specific tilt level. Value range is 0.0 to 1.0."""
        await super()._set_cover_tilt_level(level=level)
        await self.set_cover_position(position=self.current_cover_position or 0)


class CeGarage(CustomEntity):
    """Class for HomeMatic garage entities."""

    _attr_platform = HmPlatform.COVER

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_door_state: HmSensor = self._get_entity(
            field_name=FIELD_DOOR_STATE, entity_type=HmSensor
        )
        self._e_door_command: HmAction = self._get_entity(
            field_name=FIELD_DOOR_COMMAND, entity_type=HmAction
        )
        self._e_section: HmSensor = self._get_entity(
            field_name=FIELD_SECTION, entity_type=HmSensor
        )

    @value_property
    def current_cover_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._e_door_state.value == GARAGE_DOOR_STATE_OPEN:
            return 100
        if self._e_door_state.value == GARAGE_DOOR_STATE_VENTILATION_POSITION:
            return 10
        if self._e_door_state.value == GARAGE_DOOR_STATE_CLOSED:
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

    @value_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._e_door_state.value is not None:
            return str(self._e_door_state.value) == GARAGE_DOOR_STATE_CLOSED
        return None

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == GARAGE_DOOR_SECTION_OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == GARAGE_DOOR_SECTION_CLOSING
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
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomematicIP cover entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeCover,
        device_enum=EntityDefinition.IP_COVER,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_rf_cover(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomeMatic classic cover entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeCover,
        device_enum=EntityDefinition.RF_COVER,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_ip_blind(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomematicIP cover entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeIpBlind,
        device_enum=EntityDefinition.IP_COVER,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_ip_garage(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomematicIP garage entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeGarage,
        device_enum=EntityDefinition.IP_GARAGE,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_rf_blind(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomeMatic classic cover entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeBlind,
        device_enum=EntityDefinition.RF_COVER,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_rf_window_drive(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hme.BaseEntity, ...]:
    """Creates HomeMatic classic window drive entities."""
    return make_custom_entity(
        device=device,
        custom_entity_class=CeWindowDrive,
        device_enum=EntityDefinition.RF_COVER,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant
DEVICES: dict[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "263 146": CustomConfig(func=make_rf_cover, channels=(1,)),
    "263 147": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1-FM": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1-FM-2": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1-PB-FM": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1-SM": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1-SM-2": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Bl1PBU-FM": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-BlX": CustomConfig(func=make_rf_cover, channels=(1,)),
    "HM-LC-Ja1PBU-FM": CustomConfig(func=make_rf_blind, channels=(1,)),
    "HM-LC-JaX": CustomConfig(func=make_rf_blind, channels=(1,)),
    "HM-Sec-Win": CustomConfig(
        func=make_rf_window_drive,
        channels=(1,),
        extended=ExtendedConfig(
            additional_entities={
                1: (
                    "DIRECTION",
                    "WORKING",
                    "ERROR",
                ),
                2: (
                    "LEVEL",
                    "STATUS",
                ),
            }
        ),
    ),
    "HMW-LC-Bl1": CustomConfig(func=make_rf_cover, channels=(3,)),
    "HmIP-BBL": CustomConfig(func=make_ip_blind, channels=(3,)),
    "HmIP-BROLL": CustomConfig(func=make_ip_cover, channels=(3,)),
    "HmIP-DRBLI4": CustomConfig(
        func=make_ip_blind,
        channels=(9, 13, 17, 21),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ACTUAL_TEMPERATURE",),
            }
        ),
    ),
    "HmIP-FBL": CustomConfig(func=make_ip_blind, channels=(3,)),
    "HmIP-FROLL": CustomConfig(func=make_ip_cover, channels=(3,)),
    "HmIP-HDM": CustomConfig(func=make_ip_blind, channels=(0,)),
    "HmIP-MOD-HO": CustomConfig(func=make_ip_garage, channels=(1,)),
    "HmIP-MOD-TM": CustomConfig(func=make_ip_garage, channels=(1,)),
    "HmIPW-DRBL4": CustomConfig(
        func=make_ip_blind,
        channels=(1, 5, 9, 13),
        extended=ExtendedConfig(
            additional_entities={
                0: ("ACTUAL_TEMPERATURE",),
            }
        ),
    ),
    "ZEL STG RM FEP 230V": CustomConfig(func=make_rf_cover, channels=(1,)),
}

BLACKLISTED_DEVICES: tuple[str, ...] = ()
