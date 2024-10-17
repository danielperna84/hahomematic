"""
Module for entities implemented using the cover platform.

See https://www.home-assistant.io/integrations/cover/.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final

from hahomematic.const import EntityUsage, HmPlatform, Parameter
from hahomematic.converter import convert_hm_level_to_cpv
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic import HmAction, HmFloat, HmSelect, HmSensor

_LOGGER: Final = logging.getLogger(__name__)

_CLOSED_LEVEL: Final[float] = 0.0  # must be float!
_OPEN_LEVEL: Final[float] = 1.0  # must be float!
_OPEN_TILT_LEVEL: Final[float] = 1.0  # must be float!
_WD_CLOSED_LEVEL: Final[float] = -0.005  # must be float! HM-Sec-Win


class _CoverActivity(StrEnum):
    """Enum with cover activities."""

    CLOSING = "DOWN"
    OPENING = "UP"


class _CoverPosition(IntEnum):
    """Enum with cover positions."""

    OPEN = 100
    VENT = 10
    CLOSED = 0


class _GarageDoorActivity(IntEnum):
    """Enum with garage door commands."""

    CLOSING = 5
    OPENING = 2


class _GarageDoorCommand(StrEnum):
    """Enum with garage door commands."""

    CLOSE = "CLOSE"
    NOP = "NOP"
    OPEN = "OPEN"
    PARTIAL_OPEN = "PARTIAL_OPEN"
    STOP = "STOP"


class _GarageDoorState(StrEnum):
    """Enum with garage door states."""

    CLOSED = "CLOSED"
    OPEN = "OPEN"
    VENTILATION_POSITION = "VENTILATION_POSITION"
    POSITION_UNKNOWN = "_POSITION_UNKNOWN"


class _StateChangeArg(StrEnum):
    """Enum with cover state change arguments."""

    CLOSE = "close"
    OPEN = "open"
    POSITION = "position"
    TILT_CLOSE = "tilt_close"
    TILT_OPEN = "tilt_open"
    TILT_POSITION = "tilt_position"
    VENT = "vent"


class CeCover(CustomEntity):
    """Class for HomeMatic cover entities."""

    _platform = HmPlatform.COVER
    _closed_level: float = _CLOSED_LEVEL
    _open_level: float = _OPEN_LEVEL

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._command_processing_lock = asyncio.Lock()
        self._e_direction: HmSensor[str | None] = self._get_entity(
            field=Field.DIRECTION, entity_type=HmSensor[str | None]
        )
        self._e_level: HmFloat = self._get_entity(field=Field.LEVEL, entity_type=HmFloat)
        self._e_stop: HmAction = self._get_entity(field=Field.STOP, entity_type=HmAction)
        self._e_channel_level: HmSensor[float | None] = self._get_entity(
            field=Field.CHANNEL_LEVEL, entity_type=HmSensor[float | None]
        )

    @property
    def _channel_level(self) -> float:
        """Return the channel level of the cover."""
        if self._e_channel_level.value is not None and self.usage == EntityUsage.CE_PRIMARY:
            return float(self._e_channel_level.value)
        return self._e_level.value if self._e_level.value is not None else self._closed_level

    @state_property
    def current_position(self) -> int:
        """Return current position of cover."""
        return int(self._channel_level * 100)

    @bind_collector()
    async def set_position(
        self,
        position: int | None = None,
        tilt_position: int | None = None,
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
        """Move the cover to a specific position. Value range is 0.0 to 1.01."""
        if level is None:
            return
        await self._e_level.send_value(value=level, collector=collector)

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        return self._channel_level == self._closed_level

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the cover is opening."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == _CoverActivity.OPENING
        return None

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the cover is closing."""
        if self._e_direction.value is not None:
            return str(self._e_direction.value) == _CoverActivity.CLOSING
        return None

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover."""
        if not self.is_state_change(open=True):
            return
        await self._set_level(level=self._open_level, collector=collector)

    @bind_collector()
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover."""
        if not self.is_state_change(close=True):
            return
        await self._set_level(level=self._closed_level, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_stop.send_value(value=True, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            kwargs.get(_StateChangeArg.OPEN) is not None
            and self._channel_level != self._open_level
        ):
            return True
        if (
            kwargs.get(_StateChangeArg.CLOSE) is not None
            and self._channel_level != self._closed_level
        ):
            return True
        if (
            position := kwargs.get(_StateChangeArg.POSITION)
        ) is not None and position != self.current_position:
            return True
        return super().is_state_change(**kwargs)


class CeWindowDrive(CeCover):
    """Class for Homematic window drive."""

    _closed_level: float = _WD_CLOSED_LEVEL
    _open_level: float = _OPEN_LEVEL

    @state_property
    def current_position(self) -> int:
        """Return current position of cover."""
        level = self._e_level.value if self._e_level.value is not None else self._closed_level
        if level == _WD_CLOSED_LEVEL:
            level = _CLOSED_LEVEL
        elif level == _CLOSED_LEVEL:
            level = 0.01
        return int(level * 100)

    async def _set_level(
        self,
        level: float | None = None,
        tilt_level: float | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the window drive to a specific position. Value range is -0.005 to 1.01."""
        if level is None:
            return

        if level == _CLOSED_LEVEL:
            wd_level = _WD_CLOSED_LEVEL
        elif _CLOSED_LEVEL < level <= 0.01:
            wd_level = 0
        else:
            wd_level = level
        await self._e_level.send_value(value=wd_level, collector=collector, do_validate=False)


class CeBlind(CeCover):
    """Class for HomeMatic blind entities."""

    _open_tilt_level: float = _OPEN_TILT_LEVEL

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_channel_level_2: HmSensor[float | None] = self._get_entity(
            field=Field.CHANNEL_LEVEL_2, entity_type=HmSensor[float | None]
        )
        self._e_level_2: HmFloat = self._get_entity(field=Field.LEVEL_2, entity_type=HmFloat)
        self._e_combined: HmAction = self._get_entity(
            field=Field.LEVEL_COMBINED, entity_type=HmAction
        )

    @property
    def _channel_tilt_level(self) -> float:
        """Return the channel level of the tilt."""
        if self._e_channel_level_2.value is not None and self.usage == EntityUsage.CE_PRIMARY:
            return float(self._e_channel_level_2.value)
        return self._e_level_2.value if self._e_level_2.value is not None else self._closed_level

    @state_property
    def current_tilt_position(self) -> int:
        """Return current tilt position of cover."""
        return int(self._channel_tilt_level * 100)

    @property
    def _target_level(self) -> float | None:
        """Return the level of last service call."""
        if (last_value_send := self._e_level.unconfirmed_last_value_send) is not None:
            return float(last_value_send)
        return None

    @property
    def _target_tilt_level(self) -> float | None:
        """Return the tilt level of last service call."""
        if (last_value_send := self._e_level_2.unconfirmed_last_value_send) is not None:
            return float(last_value_send)
        return None

    @bind_collector(enabled=False)
    async def set_position(
        self,
        position: int | None = None,
        tilt_position: int | None = None,
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
        """
        Move the cover to a specific tilt level. Value range is 0.0 to 1.00.

        level or tilt_level may be set to None for no change.
        """
        currently_moving = False

        async with self._command_processing_lock:
            if level is not None:
                _level = level
            elif self._target_level is not None:
                # The blind moves and the target blind height is known
                currently_moving = True
                _level = self._target_level
            else:  # The blind is at a standstill and no level is explicitly requested => we remain at the current level
                _level = self._channel_level

            if tilt_level is not None:
                _tilt_level = tilt_level
            elif self._target_tilt_level is not None:
                # The blind moves and the target slat position is known
                currently_moving = True
                _tilt_level = self._target_tilt_level
            else:  # The blind is at a standstill and no tilt is explicitly desired => we remain at the current angle
                _tilt_level = self._channel_tilt_level

            if currently_moving:
                # Blind actors are buggy when sending new coordinates while they are moving. So we stop them first.
                await self._stop()

            await self._send_level(level=_level, tilt_level=_tilt_level, collector=collector)

    @bind_collector()
    async def _send_level(
        self,
        level: float,
        tilt_level: float,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Transmit a new target level to the device."""
        if self._e_combined.is_hmtype and (
            combined_parameter := self._get_combined_value(level=level, tilt_level=tilt_level)
        ):
            # don't use collector for blind combined parameter
            await self._e_combined.send_value(value=combined_parameter, collector=None)
            return

        await self._e_level_2.send_value(value=tilt_level, collector=collector)
        await super()._set_level(level=level, collector=collector)

    @bind_collector(enabled=False)
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the cover and open the tilt."""
        if not self.is_state_change(open=True, tilt_open=True):
            return
        await self._set_level(
            level=self._open_level,
            tilt_level=self._open_tilt_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the cover and close the tilt."""
        if not self.is_state_change(close=True, tilt_close=True):
            return
        await self._set_level(
            level=self._closed_level,
            tilt_level=self._closed_level,
            collector=collector,
        )

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        async with self._command_processing_lock:
            await self._stop(collector=collector)

    @bind_collector(enabled=False)
    async def _stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Do only call with _command_processing_lock held."""
        await super().stop(collector=collector)

    @bind_collector(enabled=False)
    async def open_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Open the tilt."""
        if not self.is_state_change(tilt_open=True):
            return
        await self._set_level(tilt_level=self._open_tilt_level, collector=collector)

    @bind_collector(enabled=False)
    async def close_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Close the tilt."""
        if not self.is_state_change(tilt_close=True):
            return
        await self._set_level(tilt_level=self._closed_level, collector=collector)

    @bind_collector(enabled=False)
    async def stop_tilt(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion. Use only when command_processing_lock is held."""
        await self.stop(collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            tilt_position := kwargs.get(_StateChangeArg.TILT_POSITION)
        ) is not None and tilt_position != self.current_tilt_position:
            return True
        if (
            kwargs.get(_StateChangeArg.TILT_OPEN) is not None
            and self.current_tilt_position != _CoverPosition.OPEN
        ):
            return True
        if (
            kwargs.get(_StateChangeArg.TILT_CLOSE) is not None
            and self.current_tilt_position != _CoverPosition.CLOSED
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
            levels.append(convert_hm_level_to_cpv(hm_level=level))
        if tilt_level is not None:
            levels.append(convert_hm_level_to_cpv(hm_level=tilt_level))

        if levels:
            return ",".join(levels)
        return None


class CeIpBlind(CeBlind):
    """Class for HomematicIP blind entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_operation_mode: HmSelect = self._get_entity(
            field=Field.OPERATION_MODE, entity_type=HmSelect
        )
        self._e_combined: HmAction = self._get_entity(
            field=Field.COMBINED_PARAMETER, entity_type=HmAction
        )

    @property
    def operation_mode(self) -> str | None:
        """Return operation mode of cover."""
        return self._e_operation_mode.value

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
        self._e_door_state: HmSensor[str | None] = self._get_entity(
            field=Field.DOOR_STATE, entity_type=HmSensor[str | None]
        )
        self._e_door_command: HmAction = self._get_entity(
            field=Field.DOOR_COMMAND, entity_type=HmAction
        )
        self._e_section: HmSensor[str | None] = self._get_entity(
            field=Field.SECTION, entity_type=HmSensor[str | None]
        )

    @state_property
    def current_position(self) -> int | None:
        """Return current position of the garage door ."""
        if self._e_door_state.value == _GarageDoorState.OPEN:
            return _CoverPosition.OPEN
        if self._e_door_state.value == _GarageDoorState.VENTILATION_POSITION:
            return _CoverPosition.VENT
        if self._e_door_state.value == _GarageDoorState.CLOSED:
            return _CoverPosition.CLOSED
        return None

    @bind_collector()
    async def set_position(
        self,
        position: int | None = None,
        tilt_position: int | None = None,
        collector: CallParameterCollector | None = None,
    ) -> None:
        """Move the garage door to a specific position."""
        if position is None:
            return
        if 50 < position <= 100:
            await self.open(collector=collector)
        if 10 < position <= 50:
            await self.vent(collector=collector)
        if 0 <= position <= 10:
            await self.close(collector=collector)

    @state_property
    def is_closed(self) -> bool | None:
        """Return if the garage door is closed."""
        if self._e_door_state.value is not None:
            return str(self._e_door_state.value) == _GarageDoorState.CLOSED
        return None

    @state_property
    def is_opening(self) -> bool | None:
        """Return if the garage door is opening."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == _GarageDoorActivity.OPENING
        return None

    @state_property
    def is_closing(self) -> bool | None:
        """Return if the garage door is closing."""
        if self._e_section.value is not None:
            return int(self._e_section.value) == _GarageDoorActivity.CLOSING
        return None

    @bind_collector()
    async def open(self, collector: CallParameterCollector | None = None) -> None:
        """Open the garage door."""
        if not self.is_state_change(open=True):
            return
        await self._e_door_command.send_value(value=_GarageDoorCommand.OPEN, collector=collector)

    @bind_collector()
    async def close(self, collector: CallParameterCollector | None = None) -> None:
        """Close the garage door."""
        if not self.is_state_change(close=True):
            return
        await self._e_door_command.send_value(value=_GarageDoorCommand.CLOSE, collector=collector)

    @bind_collector(enabled=False)
    async def stop(self, collector: CallParameterCollector | None = None) -> None:
        """Stop the device if in motion."""
        await self._e_door_command.send_value(value=_GarageDoorCommand.STOP, collector=collector)

    @bind_collector()
    async def vent(self, collector: CallParameterCollector | None = None) -> None:
        """Move the garage door to vent position."""
        if not self.is_state_change(vent=True):
            return
        await self._e_door_command.send_value(
            value=_GarageDoorCommand.PARTIAL_OPEN, collector=collector
        )

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            kwargs.get(_StateChangeArg.OPEN) is not None
            and self.current_position != _CoverPosition.OPEN
        ):
            return True
        if (
            kwargs.get(_StateChangeArg.VENT) is not None
            and self.current_position != _CoverPosition.VENT
        ):
            return True
        if (
            kwargs.get(_StateChangeArg.CLOSE) is not None
            and self.current_position != _CoverPosition.CLOSED
        ):
            return True
        return super().is_state_change(**kwargs)


def make_ip_cover(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeCover,
        device_profile=DeviceProfile.IP_COVER,
        custom_config=custom_config,
    )


def make_rf_cover(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic cover entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeCover,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


def make_ip_blind(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpBlind,
        device_profile=DeviceProfile.IP_COVER,
        custom_config=custom_config,
    )


def make_ip_garage(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP garage entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeGarage,
        device_profile=DeviceProfile.IP_GARAGE,
        custom_config=custom_config,
    )


def make_ip_hdm(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP cover entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpBlind,
        device_profile=DeviceProfile.IP_HDM,
        custom_config=custom_config,
    )


def make_rf_blind(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic cover entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeBlind,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


def make_rf_window_drive(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic window drive entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeWindowDrive,
        device_profile=DeviceProfile.RF_COVER,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "263 146": CustomConfig(make_ce_func=make_rf_cover),
    "263 147": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-Velux": CustomConfig(make_ce_func=make_rf_cover),  # HB-LC-Bl1-Velux
    "HM-LC-Bl1-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-FM-2": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-PB-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-SM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1-SM-2": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Bl1PBU-FM": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-BlX": CustomConfig(make_ce_func=make_rf_cover),
    "HM-LC-Ja1PBU-FM": CustomConfig(make_ce_func=make_rf_blind),
    "HM-LC-JaX": CustomConfig(make_ce_func=make_rf_blind),
    "HM-Sec-Win": CustomConfig(
        make_ce_func=make_rf_window_drive,
        channels=(1,),
        extended=ExtendedConfig(
            additional_entities={
                1: (
                    Parameter.DIRECTION,
                    Parameter.WORKING,
                    Parameter.ERROR,
                ),
                2: (
                    Parameter.LEVEL,
                    Parameter.STATUS,
                ),
            }
        ),
    ),
    "HMW-LC-Bl1": CustomConfig(make_ce_func=make_rf_cover, channels=(3,)),
    "HmIP-BBL": CustomConfig(make_ce_func=make_ip_blind, channels=(4,)),
    "HmIP-BROLL": CustomConfig(make_ce_func=make_ip_cover, channels=(4,)),
    "HmIP-DRBLI4": CustomConfig(
        make_ce_func=make_ip_blind,
        channels=(10, 14, 18, 22),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIP-FBL": CustomConfig(make_ce_func=make_ip_blind, channels=(4,)),
    "HmIP-FROLL": CustomConfig(make_ce_func=make_ip_cover, channels=(4,)),
    "HmIP-HDM": CustomConfig(make_ce_func=make_ip_hdm),
    "HmIP-MOD-HO": CustomConfig(make_ce_func=make_ip_garage),
    "HmIP-MOD-TM": CustomConfig(make_ce_func=make_ip_garage),
    "HmIPW-DRBL4": CustomConfig(
        make_ce_func=make_ip_blind,
        channels=(2, 6, 10, 14),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "ZEL STG RM FEP 230V": CustomConfig(make_ce_func=make_rf_cover),
}
hmed.ALL_DEVICES[HmPlatform.COVER] = DEVICES
