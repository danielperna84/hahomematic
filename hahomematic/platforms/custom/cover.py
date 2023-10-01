"""
Module for entities implemented using the cover platform.

See https://www.home-assistant.io/integrations/cover/.
"""
from __future__ import annotations

from enum import IntEnum, StrEnum
import logging
from typing import Any, Final

from hahomematic.const import EntityUsage, HmPlatform
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import (
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_CHANNEL_OPERATION_MODE,
    FIELD_COMBINED_PARAMETER,
    FIELD_DIRECTION,
    FIELD_DOOR_COMMAND,
    FIELD_DOOR_STATE,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_LEVEL_COMBINED,
    FIELD_SECTION,
    FIELD_STOP,
    EntityDefinition,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import value_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.number import HmFloat
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.generic.sensor import HmSensor

_LOGGER: Final = logging.getLogger(__name__)

_CLOSED: Final = 0.0  # must be float!
_OPEN: Final = 1.0  # must be float!
_WD_CLOSED: Final = -0.005  # must be float! HM-Sec-Win


class StateChangeArg(StrEnum):
    """Enum with cover state change arguments."""

    CLOSE = "close"
    OPEN = "open"
    POSITION = "position"
    TILT_CLOSE = "tilt_close"
    TILT_OPEN = "tilt_open"
    TILT_POSITION = "tilt_position"
    VENT = "vent"


class CoverActivity(StrEnum):
    """Enum with cover activities."""

    CLOSING = "DOWN"
    OPENING = "UP"


class CoverPosition(IntEnum):
    """Enum with cover positions."""

    OPEN = 100
    VENT = 10
    CLOSED = 0


class GarageDoorActivity(IntEnum):
    """Enum with garage door commands."""

    CLOSING = 5
    OPENING = 2


class GarageDoorCommand(StrEnum):
    """Enum with garage door commands."""

    CLOSE = "CLOSE"
    NOP = "NOP"
    OPEN = "OPEN"
    PARTIAL_OPEN = "PARTIAL_OPEN"
    STOP = "STOP"


class GarageDoorState(StrEnum):
    """Enum with garage door states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    VENTILATION_POSITION = "VENTILATION_POSITION"
    POSITION_UNKNOWN = "_POSITION_UNKNOWN"


class CeCover(CustomEntity):
    """Class for HomeMatic cover entities."""

    _platform = HmPlatform.COVER
    _hm_closed_state: float = _CLOSED
    _hm_open_state: float = _OPEN

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
    def _channel_level(self) -> float:
        """Return the channel level of the cover."""
        if self._e_channel_level.value is not None and self.usage == EntityUsage.CE_PRIMARY:
            return float(self._e_channel_level.value)
        return self._e_level.value if self._e_level.value is not None else self._hm_closed_state

    @value_property
    def current_position(self) -> int:
        """Return current position of cover."""
        return int(self._channel_level * 100)

    @bind_collector
    async def set_position(
        self,
        position: float | None = None,
        tilt_position: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position."""
        if not self.is_state_change(position=position):
            return
        level = min(100.0, max(0.0, position)) / 100.0 if position is not None else None
        await self._set_level(level=level, collector=collector)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific position. Value range is 0.0 to 1.0."""
        if level is None:
            return
        await self._e_level.send_value(value=level, collector=collector)

    @value_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._channel_level == self._hm_closed_state

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == CoverActivity.OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == CoverActivity.CLOSING
        return None

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""
        if not self.is_state_change(open=True):
            return
        await self._set_level(level=self._hm_open_state, collector=collector)

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""
        if not self.is_state_change(close=True):
            return
        await self._set_level(level=self._hm_closed_state, collector=collector)

    @bind_collector
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(StateChangeArg.OPEN) is not None and self._channel_level != _OPEN:
            return True
        if kwargs.get(StateChangeArg.CLOSE) is not None and self._channel_level != _CLOSED:
            return True
        if (
            position := kwargs.get(StateChangeArg.POSITION)
        ) is not None and position != self.current_position:
            return True
        return super().is_state_change(**kwargs)


class CeWindowDrive(CeCover):
    """Class for Homematic window drive."""

    _hm_closed_state: float = _WD_CLOSED
    _hm_open_state: float = _OPEN

    @value_property
    def current_position(self) -> int:
        """Return current position of cover."""
        level = self._e_level.value if self._e_level.value is not None else self._hm_closed_state
        if level == _WD_CLOSED:
            level = _CLOSED
        elif level == _CLOSED:
            level = 0.01
        return int(level * 100)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the window drive to a specific position. Value range is -0.005 to 1.0."""
        if level is None:
            return

        if level == _CLOSED:
            wd_level = _WD_CLOSED
        elif _CLOSED < level <= 0.01:
            wd_level = 0
        else:
            wd_level = level
        await self._e_level.send_value(value=wd_level, collector=collector, do_validate=False)


class CeBlind(CeCover):
    """Class for HomeMatic blind entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_channel_level_2: HmSensor = self._get_entity(
            field_name=FIELD_CHANNEL_LEVEL_2, entity_type=HmSensor
        )
        self._e_level_2: HmFloat = self._get_entity(field_name=FIELD_LEVEL_2, entity_type=HmFloat)
        self._e_combined: HmAction = self._get_entity(
            field_name=FIELD_LEVEL_COMBINED, entity_type=HmAction
        )

    @property
    def _channel_tilt_level(self) -> float:
        """Return the channel level of the tilt."""
        if self._e_channel_level_2.value is not None and self.usage == EntityUsage.CE_PRIMARY:
            return float(self._e_channel_level_2.value)
        return (
            self._e_level_2.value if self._e_level_2.value is not None else self._hm_closed_state
        )

    @value_property
    def current_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return int(self._channel_tilt_level * 100)

    @bind_collector
    async def set_position(
        self,
        position: float | None = None,
        tilt_position: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the blind to a specific position."""
        if not self.is_state_change(position=position, tilt_position=tilt_position):
            return
        level = min(100.0, max(0.0, position)) / 100.0 if position is not None else None
        tilt_level = (
            min(100.0, max(0.0, tilt_position)) / 100.0 if tilt_position is not None else None
        )
        await self._set_level(level=level, tilt_level=tilt_level, collector=collector)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the cover to a specific tilt level. Value range is 0.0 to 1.0."""
        _level = level if level is not None else self.current_position / 100.0
        _tilt_level = tilt_level if tilt_level is not None else self.current_tilt_position / 100.0
        if self._e_combined.is_hmtype and (
            combined_parameter := self._get_combined_value(level=_level, tilt_level=_tilt_level)
        ):
            await self._e_combined.send_value(value=combined_parameter, collector=collector)
            return

        await self._e_level_2.send_value(value=_tilt_level, collector=collector)
        await super()._set_level(level=_level, collector=collector)

    @bind_collector
    async def open_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Open the tilt."""
        if not self.is_state_change(tilt_open=True):
            return
        await self._set_level(tilt_level=self._hm_open_state, collector=collector)

    @bind_collector
    async def close_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""
        if not self.is_state_change(tilt_close=True):
            return
        await self._set_level(tilt_level=self._hm_closed_state, collector=collector)

    @bind_collector
    async def stop_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            tilt_position := kwargs.get(StateChangeArg.TILT_POSITION)
        ) is not None and tilt_position != self.current_tilt_position:
            return True
        if (
            kwargs.get(StateChangeArg.TILT_OPEN) is not None
            and self.current_tilt_position != CoverPosition.OPEN
        ):
            return True
        if (
            kwargs.get(StateChangeArg.TILT_CLOSE) is not None
            and self.current_tilt_position != CoverPosition.CLOSED
        ):
            return True
        return super().is_state_change(**kwargs)

    def _get_combined_value(
        self, level: float | None = None, tilt_level: float | None = None
    ) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        # the resulting hex value is based on the doubled position
        if level is not None:
            levels.append(format(int(level * 100 * 2), "#04x"))
        if tilt_level is not None:
            levels.append(format(int(tilt_level * 100 * 2), "#04x"))

        if levels:
            return ",".join(levels)
        return None


class CeIpBlind(CeBlind):
    """Class for HomematicIP blind entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_channel_operation_mode: HmSelect = self._get_entity(
            field_name=FIELD_CHANNEL_OPERATION_MODE, entity_type=HmSelect
        )
        self._e_combined: HmAction = self._get_entity(
            field_name=FIELD_COMBINED_PARAMETER, entity_type=HmAction
        )

    @value_property
    def channel_operation_mode(self) -> str | None:
        """Return channel_operation_mode of cover."""
        return self._e_channel_operation_mode.value

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover and open the tilt."""
        if not self.is_state_change(open=True, tilt_open=True):
            return
        await self._set_level(
            level=self._hm_open_state,
            tilt_level=self._hm_open_state,
            collector=collector,
        )

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover and close the tilt."""
        if not self.is_state_change(close=True, tilt_close=True):
            return
        await self._set_level(
            level=self._hm_closed_state,
            tilt_level=self._hm_closed_state,
            collector=collector,
        )

    def _get_combined_value(
        self, level: float | None = None, tilt_level: float | None = None
    ) -> str | None:
        """Return the combined parameter."""
        if level is None and tilt_level is None:
            return None
        levels: list[str] = []
        if tilt_level is not None:
            levels.append(f"L2={int(tilt_level*100)}")
        if level is not None:
            levels.append(f"L={int(level * 100)}")

        if levels:
            return ",".join(levels)
        return None


class CeGarage(CustomEntity):
    """Class for HomeMatic garage entities."""

    _platform = HmPlatform.COVER

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
    def current_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._e_door_state.value == GarageDoorState.OPEN:
            return CoverPosition.OPEN
        if self._e_door_state.value == GarageDoorState.VENTILATION_POSITION:
            return CoverPosition.VENT
        if self._e_door_state.value == GarageDoorState.CLOSED:
            return CoverPosition.CLOSED
        return None

    @bind_collector
    async def set_position(
        self,
        position: float | None = None,
        tilt_position: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the garage door to a specific position."""
        if position is None:
            return
        if 50.0 < position <= 100.0:
            await self.open(collector=collector)
        if 10.0 < position <= 50.0:
            await self.vent(collector=collector)
        if _CLOSED <= position <= 10.0:
            await self.close(collector=collector)

    @value_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._e_door_state.value is not None:
            return str(self._e_door_state.value) == GarageDoorState.CLOSED
        return None

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == GarageDoorActivity.OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == GarageDoorActivity.CLOSING
        return None

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the garage door."""
        if not self.is_state_change(open=True):
            return
        await self._e_door_command.send_value(value=GarageDoorCommand.OPEN, collector=collector)

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the garage door."""
        if not self.is_state_change(close=True):
            return
        await self._e_door_command.send_value(value=GarageDoorCommand.CLOSE, collector=collector)

    @bind_collector
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_door_command.send_value(value=GarageDoorCommand.STOP, collector=collector)

    @bind_collector
    async def vent(self, collector: CallParameterCollector | None = None) -> None:
        """Move the garage door to vent position."""
        if not self.is_state_change(vent=True):
            return
        await self._e_door_command.send_value(
            value=GarageDoorCommand.PARTIAL_OPEN, collector=collector
        )

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            kwargs.get(StateChangeArg.OPEN) is not None
            and self.current_position != CoverPosition.OPEN
        ):
            return True
        if (
            kwargs.get(StateChangeArg.VENT) is not None
            and self.current_position != CoverPosition.VENT
        ):
            return True
        if (
            kwargs.get(StateChangeArg.CLOSE) is not None
            and self.current_position != CoverPosition.CLOSED
        ):
            return True
        return super().is_state_change(**kwargs)


def make_ip_cover(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create HomematicIP cover entities."""
    return hmed.make_custom_entity(
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
) -> tuple[CustomEntity, ...]:
    """Create HomeMatic classic cover entities."""
    return hmed.make_custom_entity(
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
) -> tuple[CustomEntity, ...]:
    """Create HomematicIP cover entities."""
    return hmed.make_custom_entity(
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
) -> tuple[CustomEntity, ...]:
    """Create HomematicIP garage entities."""
    return hmed.make_custom_entity(
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
) -> tuple[CustomEntity, ...]:
    """Create HomeMatic classic cover entities."""
    return hmed.make_custom_entity(
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
) -> tuple[CustomEntity, ...]:
    """Create HomeMatic classic window drive entities."""
    return hmed.make_custom_entity(
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
hmed.ALL_DEVICES.append(DEVICES)
