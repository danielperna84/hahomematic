"""
Module for entities implemented using the cover platform.

See https://www.home-assistant.io/integrations/cover/.
"""
from __future__ import annotations

import logging
from typing import Any, Final

from hahomematic.const import HmEntityUsage, HmPlatform
from hahomematic.decorators import bind_collector
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
    HmEntityDefinition,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.entity import CallParameterCollector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.number import HmFloat
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.support import value_property

_LOGGER = logging.getLogger(__name__)

_HM_ARG_POSITION: Final = "position"
_HM_ARG_TILT_POSITION: Final = "tilt_position"
_HM_ARG_OPEN: Final = "open"
_HM_ARG_CLOSE: Final = "close"
_HM_ARG_TILT_OPEN: Final = "tilt_open"
_HM_ARG_TILT_CLOSE: Final = "tilt_close"
_HM_ARG_VENT: Final = "vent"

_HM_OPEN: Final = 1.0  # must be float!
_HM_CLOSED: Final = 0.0  # must be float!
_HM_WD_CLOSED: Final = -0.005  # must be float! HM-Sec-Win

_HM_OPENING: Final = "UP"
_HM_CLOSING: Final = "DOWN"

_GARAGE_DOOR_COMMAND_NOP: Final = "NOP"
_GARAGE_DOOR_COMMAND_OPEN: Final = "OPEN"
_GARAGE_DOOR_COMMAND_STOP: Final = "STOP"
_GARAGE_DOOR_COMMAND_CLOSE: Final = "CLOSE"
_GARAGE_DOOR_COMMAND_PARTIAL_OPEN: Final = "PARTIAL_OPEN"

_GARAGE_DOOR_SECTION_CLOSING: Final = 5
_GARAGE_DOOR_SECTION_OPENING: Final = 2

_GARAGE_DOOR_STATE_CLOSED: Final = "CLOSED"
_GARAGE_DOOR_STATE_OPEN: Final = "OPEN"
_GARAGE_DOOR_STATE_VENTILATION_POSITION: Final = "VENTILATION_POSITION"
_GARAGE_DOOR_STATE_POSITION_UNKNOWN: Final = "_POSITION_UNKNOWN"
_POSITION_OPEN: Final = 100
_POSITION_VENT: Final = 10
_POSITION_CLOSED: Final = 0


class CeCover(CustomEntity):
    """Class for HomeMatic cover entities."""

    _attr_platform = HmPlatform.COVER
    _attr_hm_closed_state: float = _HM_CLOSED
    _attr_hm_open_state: float = _HM_OPEN

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
        if self._e_channel_level.value is not None and self.usage == HmEntityUsage.CE_PRIMARY:
            return float(self._e_channel_level.value)
        return (
            self._e_level.value if self._e_level.value is not None else self._attr_hm_closed_state
        )

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
        return self._channel_level == self._attr_hm_closed_state

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == _HM_OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == _HM_CLOSING
        return None

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""
        if not self.is_state_change(open=True):
            return
        await self._set_level(level=self._attr_hm_open_state, collector=collector)

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""
        if not self.is_state_change(close=True):
            return
        await self._set_level(level=self._attr_hm_closed_state, collector=collector)

    @bind_collector
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_HM_ARG_OPEN) is not None and self._channel_level != _HM_OPEN:
            return True
        if kwargs.get(_HM_ARG_CLOSE) is not None and self._channel_level != _HM_CLOSED:
            return True
        if (
            position := kwargs.get(_HM_ARG_POSITION)
        ) is not None and position != self.current_position:
            return True
        return super().is_state_change(**kwargs)


class CeWindowDrive(CeCover):
    """Class for Homematic window drive."""

    _attr_hm_closed_state: float = _HM_WD_CLOSED
    _attr_hm_open_state: float = _HM_OPEN

    @value_property
    def current_position(self) -> int:
        """Return current position of cover."""
        level = (
            self._e_level.value if self._e_level.value is not None else self._attr_hm_closed_state
        )
        if level == _HM_WD_CLOSED:
            level = _HM_CLOSED
        elif level == _HM_CLOSED:
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

        if level == _HM_CLOSED:
            wd_level = _HM_WD_CLOSED
        elif _HM_CLOSED < level <= 0.01:
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
        if self._e_channel_level_2.value is not None and self.usage == HmEntityUsage.CE_PRIMARY:
            return float(self._e_channel_level_2.value)
        return (
            self._e_level_2.value
            if self._e_level_2.value is not None
            else self._attr_hm_closed_state
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
        await self._set_level(tilt_level=self._attr_hm_open_state, collector=collector)

    @bind_collector
    async def close_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""
        if not self.is_state_change(tilt_close=True):
            return
        await self._set_level(tilt_level=self._attr_hm_closed_state, collector=collector)

    @bind_collector
    async def stop_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            tilt_position := kwargs.get(_HM_ARG_TILT_POSITION)
        ) is not None and tilt_position != self.current_tilt_position:
            return True
        if (
            kwargs.get(_HM_ARG_TILT_OPEN) is not None
            and self.current_tilt_position != _POSITION_OPEN
        ):
            return True
        if (
            kwargs.get(_HM_ARG_TILT_CLOSE) is not None
            and self.current_tilt_position != _POSITION_CLOSED
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
            level=self._attr_hm_open_state,
            tilt_level=self._attr_hm_open_state,
            collector=collector,
        )

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover and close the tilt."""
        if not self.is_state_change(close=True, tilt_close=True):
            return
        await self._set_level(
            level=self._attr_hm_closed_state,
            tilt_level=self._attr_hm_closed_state,
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
    def current_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._e_door_state.value == _GARAGE_DOOR_STATE_OPEN:
            return _POSITION_OPEN
        if self._e_door_state.value == _GARAGE_DOOR_STATE_VENTILATION_POSITION:
            return _POSITION_VENT
        if self._e_door_state.value == _GARAGE_DOOR_STATE_CLOSED:
            return _POSITION_CLOSED
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
        if _HM_CLOSED <= position <= 10.0:
            await self.close(collector=collector)

    @value_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._e_door_state.value is not None:
            return str(self._e_door_state.value) == _GARAGE_DOOR_STATE_CLOSED
        return None

    @value_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == _GARAGE_DOOR_SECTION_OPENING
        return None

    @value_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == _GARAGE_DOOR_SECTION_CLOSING
        return None

    @bind_collector
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the garage door."""
        if not self.is_state_change(open=True):
            return
        await self._e_door_command.send_value(value=_GARAGE_DOOR_COMMAND_OPEN, collector=collector)

    @bind_collector
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the garage door."""
        if not self.is_state_change(close=True):
            return
        await self._e_door_command.send_value(
            value=_GARAGE_DOOR_COMMAND_CLOSE, collector=collector
        )

    @bind_collector
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_door_command.send_value(value=_GARAGE_DOOR_COMMAND_STOP, collector=collector)

    @bind_collector
    async def vent(self, collector: CallParameterCollector | None = None) -> None:
        """Move the garage door to vent position."""
        if not self.is_state_change(vent=True):
            return
        await self._e_door_command.send_value(
            value=_GARAGE_DOOR_COMMAND_PARTIAL_OPEN, collector=collector
        )

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if kwargs.get(_HM_ARG_OPEN) is not None and self.current_position != _POSITION_OPEN:
            return True
        if kwargs.get(_HM_ARG_VENT) is not None and self.current_position != _POSITION_VENT:
            return True
        if kwargs.get(_HM_ARG_CLOSE) is not None and self.current_position != _POSITION_CLOSED:
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
        device_enum=HmEntityDefinition.IP_COVER,
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
        device_enum=HmEntityDefinition.RF_COVER,
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
        device_enum=HmEntityDefinition.IP_COVER,
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
        device_enum=HmEntityDefinition.IP_GARAGE,
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
        device_enum=HmEntityDefinition.RF_COVER,
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
        device_enum=HmEntityDefinition.RF_COVER,
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
