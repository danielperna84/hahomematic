"""
Module for entities implemented using the climate platform.

See https://www.home-assistant.io/integrations/climate/.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final, cast

from hahomematic.const import HmPlatform, ParamsetKey
from hahomematic.exceptions import ClientException, HaHomematicException, ValidationException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig
from hahomematic.platforms.decorators import config_property, service, state_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic import (
    HmAction,
    HmBinarySensor,
    HmFloat,
    HmInteger,
    HmSelect,
    HmSensor,
    HmSwitch,
)

_LOGGER: Final = logging.getLogger(__name__)

# HA constants
_CLOSED_LEVEL: Final = 0.0
_DEFAULT_TEMPERATURE_STEP: Final = 0.5
_OFF_TEMPERATURE: Final = 4.5
_PARTY_DATE_FORMAT: Final = "%Y_%m_%d %H:%M"
_PARTY_INIT_DATE: Final = "2000_01_01 00:00"
_RAW_SCHEDULE_DICT = dict[str, float | int]
_TEMP_CELSIUS: Final = "°C"
SCHEDULE_SLOT_RANGE: Final = range(1, 14)
SCHEDULE_TIME_RANGE: Final = range(1441)
HM_PRESET_MODE_PREFIX: Final = "week_program_"


class _ModeHm(StrEnum):
    """Enum with the HM modes."""

    AUTO = "AUTO-MODE"  # 0
    AWAY = "PARTY-MODE"  # 2
    BOOST = "BOOST-MODE"  # 3
    MANU = "MANU-MODE"  # 1


class _ModeHmIP(IntEnum):
    """Enum with the HmIP modes."""

    AUTO = 0
    AWAY = 2
    MANU = 1


class _StateChangeArg(StrEnum):
    """Enum with climate state change arguments."""

    HVAC_MODE = "hvac_mode"
    PRESET_MODE = "preset_mode"
    TEMPERATURE = "temperature"


class HmHvacAction(StrEnum):
    """Enum with the hvac actions."""

    COOL = "cooling"
    HEAT = "heating"
    IDLE = "idle"
    OFF = "off"


class HmHvacMode(StrEnum):
    """Enum with the hvac modes."""

    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    OFF = "off"


class HmPresetMode(StrEnum):
    """Enum with preset modes."""

    AWAY = "away"
    BOOST = "boost"
    COMFORT = "comfort"
    ECO = "eco"
    NONE = "none"
    WEEK_PROGRAM_1 = "week_program_1"
    WEEK_PROGRAM_2 = "week_program_2"
    WEEK_PROGRAM_3 = "week_program_3"
    WEEK_PROGRAM_4 = "week_program_4"
    WEEK_PROGRAM_5 = "week_program_5"
    WEEK_PROGRAM_6 = "week_program_6"


class ScheduleSlotType(StrEnum):
    """Enum for climate item type."""

    ENDTIME = "ENDTIME"
    STARTTIME = "STARTTIME"
    TEMPERATURE = "TEMPERATURE"


RELEVANT_SLOT_TYPES: Final = (ScheduleSlotType.ENDTIME, ScheduleSlotType.TEMPERATURE)


class ScheduleProfile(StrEnum):
    """Enum for climate profiles."""

    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"
    P5 = "P5"
    P6 = "P6"


class ScheduleWeekday(StrEnum):
    """Enum for climate week days."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


SIMPLE_WEEKDAY_LIST = list[dict[ScheduleSlotType, str | float]]
SIMPLE_PROFILE_DICT = dict[ScheduleWeekday, SIMPLE_WEEKDAY_LIST]
WEEKDAY_DICT = dict[int, dict[ScheduleSlotType, str | float]]
PROFILE_DICT = dict[ScheduleWeekday, WEEKDAY_DICT]
_SCHEDULE_DICT = dict[ScheduleProfile, PROFILE_DICT]


class BaseClimateEntity(CustomEntity):
    """Base HomeMatic climate entity."""

    _platform = HmPlatform.CLIMATE
    _supports_schedule = False

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_humidity: HmSensor[int | None] = self._get_entity(
            field=Field.HUMIDITY, entity_type=HmSensor[int | None]
        )
        self._e_setpoint: HmFloat = self._get_entity(field=Field.SETPOINT, entity_type=HmFloat)
        self._e_temperature: HmSensor[float | None] = self._get_entity(
            field=Field.TEMPERATURE, entity_type=HmSensor[float | None]
        )
        self._e_temperature_maximum: HmFloat = self._get_entity(
            field=Field.TEMPERATURE_MAXIMUM, entity_type=HmFloat
        )
        self._e_temperature_minimum: HmFloat = self._get_entity(
            field=Field.TEMPERATURE_MINIMUM, entity_type=HmFloat
        )

    @config_property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return _TEMP_CELSIUS

    @state_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._e_temperature_minimum.value is not None:
            min_temp = float(self._e_temperature_minimum.value)
        else:
            min_temp = self._e_setpoint.min

        if min_temp == _OFF_TEMPERATURE:
            return min_temp + _DEFAULT_TEMPERATURE_STEP
        return min_temp

    @state_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._e_temperature_maximum.value is not None:
            return float(self._e_temperature_maximum.value)
        return self._e_setpoint.max  # type: ignore[no-any-return]

    @state_property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._e_humidity.value

    @state_property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._e_temperature.value

    @state_property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._e_setpoint.value

    @config_property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return _DEFAULT_TEMPERATURE_STEP

    @state_property
    def preset_mode(self) -> HmPresetMode:
        """Return the current preset mode."""
        return HmPresetMode.NONE

    @state_property
    def preset_modes(self) -> tuple[HmPresetMode, ...]:
        """Return available preset modes."""
        return (HmPresetMode.NONE,)

    @state_property
    def hvac_action(self) -> HmHvacAction | None:
        """Return the hvac action."""
        return None

    @state_property
    def hvac_mode(self) -> HmHvacMode:
        """Return hvac operation mode."""
        return HmHvacMode.HEAT

    @state_property
    def hvac_modes(self) -> tuple[HmHvacMode, ...]:
        """Return the available hvac operation modes."""
        return (HmHvacMode.HEAT,)

    @property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return False

    @property
    def _min_or_target_temperature(self) -> float:
        """Return the min or target temperature."""
        if (temperature := self.target_temperature or self.min_temp) < self.min_temp:
            return self.min_temp
        return temperature

    @bind_collector()
    async def set_temperature(
        self,
        temperature: float,
        collector: CallParameterCollector | None = None,
        do_validate: bool = True,
    ) -> None:
        """Set new target temperature."""
        if not self.is_state_change(temperature=temperature):
            return
        await self._e_setpoint.send_value(
            value=temperature, collector=collector, do_validate=do_validate
        )

    @bind_collector()
    async def set_hvac_mode(
        self, hvac_mode: HmHvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""

    @bind_collector()
    async def set_preset_mode(
        self, preset_mode: HmPresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""

    @service()
    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""

    @service()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""

    @service()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            temperature := kwargs.get(_StateChangeArg.TEMPERATURE)
        ) is not None and temperature != self.target_temperature:
            return True
        if (
            hvac_mode := kwargs.get(_StateChangeArg.HVAC_MODE)
        ) is not None and hvac_mode != self.hvac_mode:
            return True
        if (
            preset_mode := kwargs.get(_StateChangeArg.PRESET_MODE)
        ) is not None and preset_mode != self.preset_mode:
            return True
        return super().is_state_change(**kwargs)

    @service()
    async def get_profile(self, profile: ScheduleProfile) -> PROFILE_DICT:
        """Return a schedule by climate profile."""
        if not self._supports_schedule:
            raise HaHomematicException(f"Schedule is not supported by device {self._device.name}")
        schedule_data = await self._get_schedule(profile=profile)
        return schedule_data.get(profile, {})

    @service()
    async def get_profile_weekday(
        self, profile: ScheduleProfile, weekday: ScheduleWeekday
    ) -> WEEKDAY_DICT:
        """Return a schedule by climate profile."""
        if not self._supports_schedule:
            raise HaHomematicException(f"Schedule is not supported by device {self._device.name}")
        schedule_data = await self._get_schedule(profile=profile, weekday=weekday)
        return schedule_data.get(profile, {}).get(weekday, {})

    async def _get_schedule(
        self, profile: ScheduleProfile | None = None, weekday: ScheduleWeekday | None = None
    ) -> _SCHEDULE_DICT:
        """Get the schedule."""
        schedule_data: _SCHEDULE_DICT = {}
        try:
            raw_schedule = await self._client.get_paramset(
                address=self._channel.address,
                paramset_key=ParamsetKey.MASTER,
            )
        except ClientException as cex:
            self._supports_schedule = False
            raise HaHomematicException(
                f"Schedule is not supported by device {self._device.name}"
            ) from cex

        for line, slot_value in raw_schedule.items():
            if not line.startswith("P"):
                continue
            line_split = line.split("_")
            if len(line_split) != 4:
                continue
            p, et, w, no = line_split
            _profile = ScheduleProfile(p)
            if profile and profile != _profile:
                continue
            _slot_type = ScheduleSlotType(et)
            _weekday = ScheduleWeekday(w)
            if weekday and weekday != _weekday:
                continue
            _slot_no = int(no)

            _add_to_schedule_data(
                schedule_data=schedule_data,
                profile=_profile,
                weekday=_weekday,
                slot_no=_slot_no,
                slot_type=_slot_type,
                slot_value=slot_value,
            )

        return schedule_data

    @service()
    async def set_profile(self, profile: ScheduleProfile, profile_data: PROFILE_DICT) -> None:
        """Set a profile to device."""
        self._validate_profile(profile=profile, profile_data=profile_data)
        schedule_data: _SCHEDULE_DICT = {}
        for weekday, weekday_data in profile_data.items():
            for slot_no, slot in weekday_data.items():
                for slot_type, slot_value in slot.items():
                    _add_to_schedule_data(
                        schedule_data=schedule_data,
                        profile=profile,
                        weekday=weekday,
                        slot_no=slot_no,
                        slot_type=slot_type,
                        slot_value=slot_value,
                    )
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.MASTER,
            values=_get_raw_paramset(schedule_data=schedule_data),
        )

    @service()
    async def set_simple_profile(
        self,
        profile: ScheduleProfile,
        base_temperature: float,
        simple_profile_data: SIMPLE_PROFILE_DICT,
    ) -> None:
        """Set a profile to device."""
        profile_data = self._validate_and_convert_simple_to_profile(
            base_temperature=base_temperature, simple_profile_data=simple_profile_data
        )
        await self.set_profile(profile=profile, profile_data=profile_data)

    @service()
    async def set_profile_weekday(
        self, profile: ScheduleProfile, weekday: ScheduleWeekday, weekday_data: WEEKDAY_DICT
    ) -> None:
        """Store a profile to device."""
        self._validate_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)
        schedule_data: _SCHEDULE_DICT = {}
        for slot_no, slot in weekday_data.items():
            for slot_type, slot_value in slot.items():
                _add_to_schedule_data(
                    schedule_data=schedule_data,
                    profile=profile,
                    weekday=weekday,
                    slot_no=slot_no,
                    slot_type=slot_type,
                    slot_value=slot_value,
                )
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.MASTER,
            values=_get_raw_paramset(schedule_data=schedule_data),
        )

    @service()
    async def set_simple_profile_weekday(
        self,
        profile: ScheduleProfile,
        weekday: ScheduleWeekday,
        base_temperature: float,
        simple_weekday_list: SIMPLE_WEEKDAY_LIST,
    ) -> None:
        """Store a simple weekday profile to device."""
        weekday_data = self._validate_and_convert_simple_to_profile_weekday(
            base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
        )
        await self.set_profile_weekday(profile=profile, weekday=weekday, weekday_data=weekday_data)

    def _validate_and_convert_simple_to_profile(
        self, base_temperature: float, simple_profile_data: SIMPLE_PROFILE_DICT
    ) -> PROFILE_DICT:
        """Convert simple profile dict to profile dict."""
        profile_dict: PROFILE_DICT = {}
        for day, simple_weekday_list in simple_profile_data.items():
            profile_dict[day] = self._validate_and_convert_simple_to_profile_weekday(
                base_temperature=base_temperature, simple_weekday_list=simple_weekday_list
            )
        return profile_dict

    def _validate_and_convert_simple_to_profile_weekday(
        self, base_temperature: float, simple_weekday_list: SIMPLE_WEEKDAY_LIST
    ) -> WEEKDAY_DICT:
        """Convert simple weekday list to weekday dict."""
        if not self.min_temp <= base_temperature <= self.max_temp:
            raise ValidationException(
                f"VALIDATE_SIMPLE_PROFILE: Base temperature {base_temperature} not in valid range (min: {self.min_temp}, "
                f"max: {self.max_temp})"
            )

        weekday_data: WEEKDAY_DICT = {}
        sorted_simple_weekday_list = _sort_simple_weekday_list(
            simple_weekday_list=simple_weekday_list
        )
        previous_endtime = "00:00"
        slot_no = 1
        for slot in sorted_simple_weekday_list:
            if (starttime := slot.get(ScheduleSlotType.STARTTIME)) is None:
                raise ValidationException("VALIDATE_SIMPLE_PROFILE: STARTTIME is missing.")
            if (endtime := slot.get(ScheduleSlotType.ENDTIME)) is None:
                raise ValidationException("VALIDATE_SIMPLE_PROFILE: ENDTIME is missing.")
            if (temperature := slot.get(ScheduleSlotType.TEMPERATURE)) is None:
                raise ValidationException("VALIDATE_SIMPLE_PROFILE: TEMPERATURE is missing.")

            if _convert_time_str_to_minutes(str(starttime)) < _convert_time_str_to_minutes(
                previous_endtime
            ):
                raise ValidationException(
                    f"VALIDATE_SIMPLE_PROFILE: Timespans are overlapping with a previous slot for starttime: {starttime} / endtime: {endtime}"
                )

            if not self.min_temp <= float(temperature) <= self.max_temp:
                raise ValidationException(
                    f"VALIDATE_SIMPLE_PROFILE: Temperature {temperature} not in valid range (min: {self.min_temp}, "
                    f"max: {self.max_temp}) for starttime: {starttime} / endtime: {endtime}"
                )

            if _convert_time_str_to_minutes(str(starttime)) > _convert_time_str_to_minutes(
                previous_endtime
            ):
                weekday_data[slot_no] = {
                    ScheduleSlotType.ENDTIME: starttime,
                    ScheduleSlotType.TEMPERATURE: base_temperature,
                }
                slot_no += 1

            weekday_data[slot_no] = {
                ScheduleSlotType.ENDTIME: endtime,
                ScheduleSlotType.TEMPERATURE: temperature,
            }
            previous_endtime = str(endtime)
            slot_no += 1

        return _fillup_weekday_data(base_temperature=base_temperature, weekday_data=weekday_data)

    def _validate_profile(self, profile: ScheduleProfile, profile_data: PROFILE_DICT) -> None:
        """Validate the profile."""
        for weekday, weekday_data in profile_data.items():
            self._validate_profile_weekday(
                profile=profile, weekday=weekday, weekday_data=weekday_data
            )

    def _validate_profile_weekday(
        self,
        profile: ScheduleProfile,
        weekday: ScheduleWeekday,
        weekday_data: WEEKDAY_DICT,
    ) -> None:
        """Validate the profile weekday."""
        previous_endtime = 0
        for no in SCHEDULE_SLOT_RANGE:
            if no not in weekday_data:
                raise ValidationException(
                    f"VALIDATE_PROFILE: slot no {no} is missing in profile: {profile} / weekday: {weekday}"
                )
            slot = weekday_data[no]
            for slot_type in RELEVANT_SLOT_TYPES:
                if slot_type not in slot:
                    raise ValidationException(
                        f"VALIDATE_PROFILE: slot type {slot_type} is missing in profile: "
                        f"{profile} / weekday: {weekday} / slot_no: {no}"
                    )
                temperature = float(weekday_data[no][ScheduleSlotType.TEMPERATURE])
                if not self.min_temp <= temperature <= self.max_temp:
                    raise ValidationException(
                        f"VALIDATE_PROFILE: Temperature {temperature} not in valid range (min: {self.min_temp}, "
                        f"max: {self.max_temp}) for profile: {profile} / weekday: {weekday} / slot_no: {no}"
                    )

                endtime_str = str(weekday_data[no][ScheduleSlotType.ENDTIME])
                if endtime := _convert_time_str_to_minutes(time_str=endtime_str):
                    if endtime not in SCHEDULE_TIME_RANGE:
                        raise ValidationException(
                            f"VALIDATE_PROFILE: Time {endtime_str} must be between {_convert_minutes_to_time_str(minutes=SCHEDULE_TIME_RANGE.start)} and "
                            f"{_convert_minutes_to_time_str(minutes=SCHEDULE_TIME_RANGE.stop - 1)} for profile: {profile} / weekday: {weekday} / slot_no: {no}"
                        )
                    if endtime < previous_endtime:
                        raise ValidationException(
                            f"VALIDATE_PROFILE: Time sequence must be rising. {endtime_str} is lower than the previous "
                            f"value {_convert_minutes_to_time_str(minutes=previous_endtime)} for profile: {profile} / weekday: {weekday} / slot_no: {no}"
                        )
                previous_endtime = endtime


class CeSimpleRfThermostat(BaseClimateEntity):
    """Simple classic HomeMatic thermostat HM-CC-TC."""


class CeRfThermostat(BaseClimateEntity):
    """Classic HomeMatic thermostat like HM-CC-RT-DN."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_boost_mode: HmAction = self._get_entity(
            field=Field.BOOST_MODE, entity_type=HmAction
        )
        self._e_auto_mode: HmAction = self._get_entity(field=Field.AUTO_MODE, entity_type=HmAction)
        self._e_manu_mode: HmAction = self._get_entity(field=Field.MANU_MODE, entity_type=HmAction)
        self._e_comfort_mode: HmAction = self._get_entity(
            field=Field.COMFORT_MODE, entity_type=HmAction
        )
        self._e_lowering_mode: HmAction = self._get_entity(
            field=Field.LOWERING_MODE, entity_type=HmAction
        )
        self._e_control_mode: HmSensor[str | None] = self._get_entity(
            field=Field.CONTROL_MODE, entity_type=HmSensor[str | None]
        )
        self._e_valve_state: HmSensor[int | None] = self._get_entity(
            field=Field.VALVE_STATE, entity_type=HmSensor[int | None]
        )

    @state_property
    def hvac_action(self) -> HmHvacAction | None:
        """Return the hvac action."""
        if self._e_valve_state.value is None:
            return None
        if self.hvac_mode == HmHvacMode.OFF:
            return HmHvacAction.OFF
        if self._e_valve_state.value and self._e_valve_state.value > 0:
            return HmHvacAction.HEAT
        return HmHvacAction.IDLE

    @state_property
    def hvac_mode(self) -> HmHvacMode:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return HmHvacMode.OFF
        if self._e_control_mode.value == _ModeHm.MANU:
            return HmHvacMode.HEAT
        return HmHvacMode.AUTO

    @state_property
    def hvac_modes(self) -> tuple[HmHvacMode, ...]:
        """Return the available hvac operation modes."""
        return (HmHvacMode.AUTO, HmHvacMode.HEAT, HmHvacMode.OFF)

    @state_property
    def preset_mode(self) -> HmPresetMode:
        """Return the current preset mode."""
        if self._e_control_mode.value is None:
            return HmPresetMode.NONE
        if self._e_control_mode.value == _ModeHm.BOOST:
            return HmPresetMode.BOOST
        if self._e_control_mode.value == _ModeHm.AWAY:
            return HmPresetMode.AWAY
        return HmPresetMode.NONE

    @state_property
    def preset_modes(self) -> tuple[HmPresetMode, ...]:
        """Return available preset modes."""
        return (
            HmPresetMode.BOOST,
            HmPresetMode.COMFORT,
            HmPresetMode.ECO,
            HmPresetMode.NONE,
        )

    @property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return True

    @bind_collector()
    async def set_hvac_mode(
        self, hvac_mode: HmHvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""
        if not self.is_state_change(hvac_mode=hvac_mode):
            return
        if hvac_mode == HmHvacMode.AUTO:
            await self._e_auto_mode.send_value(value=True, collector=collector)
        elif hvac_mode == HmHvacMode.HEAT:
            await self._e_manu_mode.send_value(
                value=self._min_or_target_temperature, collector=collector
            )
        elif hvac_mode == HmHvacMode.OFF:
            await self._e_manu_mode.send_value(value=self.target_temperature, collector=collector)
            # Disable validation here to allow setting a value,
            # that is out of the validation range.
            await self.set_temperature(
                temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False
            )

    @bind_collector()
    async def set_preset_mode(
        self, preset_mode: HmPresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""
        if not self.is_state_change(preset_mode=preset_mode):
            return
        if preset_mode == HmPresetMode.BOOST:
            await self._e_boost_mode.send_value(value=True, collector=collector)
        elif preset_mode == HmPresetMode.COMFORT:
            await self._e_comfort_mode.send_value(value=True, collector=collector)
        elif preset_mode == HmPresetMode.ECO:
            await self._e_lowering_mode.send_value(value=True, collector=collector)

    @service()
    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value=_party_mode_code(start=start, end=end, away_temperature=away_temperature),
        )

    @service()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    @service()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        start = datetime.now() - timedelta(hours=11)
        end = datetime.now() - timedelta(hours=10)

        await self._client.set_value(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value=_party_mode_code(start=start, end=end, away_temperature=12.0),
        )


def _party_mode_code(start: datetime, end: datetime, away_temperature: float) -> str:
    """
    Create the party mode code.

    e.g. 21.5,1200,20,10,16,1380,20,10,16
    away_temperature,start_minutes_of_day, day(2), month(2), year(2), end_minutes_of_day, day(2), month(2), year(2)
    """
    return f"{away_temperature:.1f},{start.hour*60+start.minute},{start.strftime('%d,%m,%y')},{end.hour*60+end.minute},{end.strftime('%d,%m,%y')}"


class CeIpThermostat(BaseClimateEntity):
    """HomematicIP thermostat like HmIP-eTRV-B."""

    _supports_schedule = True

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_active_profile: HmInteger = self._get_entity(
            field=Field.ACTIVE_PROFILE, entity_type=HmInteger
        )
        self._e_boost_mode: HmSwitch = self._get_entity(
            field=Field.BOOST_MODE, entity_type=HmSwitch
        )
        self._e_control_mode: HmAction = self._get_entity(
            field=Field.CONTROL_MODE, entity_type=HmAction
        )
        self._e_heating_mode: HmSelect = self._get_entity(
            field=Field.HEATING_COOLING, entity_type=HmSelect
        )
        self._e_party_mode: HmBinarySensor = self._get_entity(
            field=Field.PARTY_MODE, entity_type=HmBinarySensor
        )
        self._e_set_point_mode: HmInteger = self._get_entity(
            field=Field.SET_POINT_MODE, entity_type=HmInteger
        )
        self._e_level: HmFloat = self._get_entity(field=Field.LEVEL, entity_type=HmFloat)
        self._e_state: HmBinarySensor = self._get_entity(
            field=Field.STATE, entity_type=HmBinarySensor
        )

    @property
    def _is_heating_mode(self) -> bool:
        """Return the heating_mode of the device."""
        if self._e_heating_mode.value is not None:
            return str(self._e_heating_mode.value) == "HEATING"
        return True

    @state_property
    def hvac_action(self) -> HmHvacAction | None:
        """Return the hvac action."""
        if self._e_state.value is None and self._e_level.value is None:
            return None
        if self.hvac_mode == HmHvacMode.OFF:
            return HmHvacAction.OFF
        if self._e_state.value is True or (
            self._e_level.value and self._e_level.value > _CLOSED_LEVEL
        ):
            return HmHvacAction.HEAT if self._is_heating_mode else HmHvacAction.COOL
        return HmHvacAction.IDLE

    @state_property
    def hvac_mode(self) -> HmHvacMode:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return HmHvacMode.OFF
        if self._e_set_point_mode.value == _ModeHmIP.MANU:
            return HmHvacMode.HEAT if self._is_heating_mode else HmHvacMode.COOL
        if self._e_set_point_mode.value == _ModeHmIP.AUTO:
            return HmHvacMode.AUTO
        return HmHvacMode.AUTO

    @state_property
    def hvac_modes(self) -> tuple[HmHvacMode, ...]:
        """Return the available hvac operation modes."""
        return (
            HmHvacMode.AUTO,
            HmHvacMode.HEAT if self._is_heating_mode else HmHvacMode.COOL,
            HmHvacMode.OFF,
        )

    @state_property
    def preset_mode(self) -> HmPresetMode:
        """Return the current preset mode."""
        if self._e_boost_mode.value:
            return HmPresetMode.BOOST
        if self._e_set_point_mode.value == _ModeHmIP.AWAY:
            return HmPresetMode.AWAY
        if self.hvac_mode == HmHvacMode.AUTO:
            return self._current_profile_name if self._current_profile_name else HmPresetMode.NONE
        return HmPresetMode.NONE

    @state_property
    def preset_modes(self) -> tuple[HmPresetMode, ...]:
        """Return available preset modes."""
        presets = [HmPresetMode.BOOST, HmPresetMode.NONE]
        if self.hvac_mode == HmHvacMode.AUTO:
            presets.extend(self._profile_names)
        return tuple(presets)

    @property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return True

    @bind_collector()
    async def set_hvac_mode(
        self, hvac_mode: HmHvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""
        if not self.is_state_change(hvac_mode=hvac_mode):
            return
        # if switching hvac_mode then disable boost_mode
        if self._e_boost_mode.value:
            await self.set_preset_mode(preset_mode=HmPresetMode.NONE, collector=collector)

        if hvac_mode == HmHvacMode.AUTO:
            await self._e_control_mode.send_value(value=_ModeHmIP.AUTO, collector=collector)
        elif hvac_mode in (HmHvacMode.HEAT, HmHvacMode.COOL):
            await self._e_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(
                temperature=self._min_or_target_temperature, collector=collector
            )
        elif hvac_mode == HmHvacMode.OFF:
            await self._e_control_mode.send_value(value=_ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector)

    @bind_collector()
    async def set_preset_mode(
        self, preset_mode: HmPresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""
        if not self.is_state_change(preset_mode=preset_mode):
            return
        if preset_mode == HmPresetMode.BOOST:
            await self._e_boost_mode.send_value(value=True, collector=collector)
        elif preset_mode == HmPresetMode.NONE:
            await self._e_boost_mode.send_value(value=False, collector=collector)
        elif preset_mode in self._profile_names:
            if self.hvac_mode != HmHvacMode.AUTO:
                await self.set_hvac_mode(hvac_mode=HmHvacMode.AUTO, collector=collector)
                await self._e_boost_mode.send_value(value=False, collector=collector)
            if profile_idx := self._profiles.get(preset_mode):
                await self._e_active_profile.send_value(value=profile_idx, collector=collector)

    @service()
    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": _ModeHmIP.AWAY,
                "SET_POINT_TEMPERATURE": away_temperature,
                "PARTY_TIME_START": start.strftime(_PARTY_DATE_FORMAT),
                "PARTY_TIME_END": end.strftime(_PARTY_DATE_FORMAT),
            },
        )

    @service()
    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    @service()
    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self._client.put_paramset(
            channel_address=self._channel.address,
            paramset_key=ParamsetKey.VALUES,
            values={
                "SET_POINT_MODE": _ModeHmIP.AWAY,
                "PARTY_TIME_START": _PARTY_INIT_DATE,
                "PARTY_TIME_END": _PARTY_INIT_DATE,
            },
        )

    @property
    def _profile_names(self) -> tuple[HmPresetMode, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _current_profile_name(self) -> HmPresetMode | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        if self._e_active_profile.value is not None:
            return inv_profiles.get(int(self._e_active_profile.value))
        return None

    @property
    def _profiles(self) -> Mapping[HmPresetMode, int]:
        """Return the profile groups."""
        profiles: dict[HmPresetMode, int] = {}
        if self._e_active_profile.min and self._e_active_profile.max:
            for i in range(self._e_active_profile.min, self._e_active_profile.max + 1):
                profiles[HmPresetMode(f"{HM_PRESET_MODE_PREFIX}{i}")] = i

        return profiles


def _convert_minutes_to_time_str(minutes: int) -> str:
    """Convert minutes to a time string."""
    try:
        return f"{minutes//60:0=2}:{minutes%60:0=2}"
    except Exception as ex:
        raise ValidationException(ex) from ex


def _convert_time_str_to_minutes(time_str: str) -> int:
    """Convert minutes to a time string."""
    try:
        h, m = time_str.split(":")
        return (int(h) * 60) + int(m)
    except Exception as ex:
        raise ValidationException(
            f"Failed to convert time {time_str}. Format must be hh:mm."
        ) from ex


def _sort_simple_weekday_list(simple_weekday_list: SIMPLE_WEEKDAY_LIST) -> SIMPLE_WEEKDAY_LIST:
    """Sort simple weekday list."""
    simple_weekday_dict = sorted(
        {
            _convert_time_str_to_minutes(str(slot[ScheduleSlotType.STARTTIME])): slot
            for slot in simple_weekday_list
        }.items()
    )
    return [slot[1] for slot in simple_weekday_dict]


def _fillup_weekday_data(base_temperature: float, weekday_data: WEEKDAY_DICT) -> WEEKDAY_DICT:
    """Fillup weekday data."""
    for slot_no in SCHEDULE_SLOT_RANGE:
        if slot_no not in weekday_data:
            weekday_data[slot_no] = {
                ScheduleSlotType.ENDTIME: "24:00",
                ScheduleSlotType.TEMPERATURE: base_temperature,
            }

    return weekday_data


def _get_raw_paramset(schedule_data: _SCHEDULE_DICT) -> _RAW_SCHEDULE_DICT:
    """Return the raw paramset."""
    raw_paramset: _RAW_SCHEDULE_DICT = {}
    for profile, profile_data in schedule_data.items():
        for weekday, weekday_data in profile_data.items():
            for slot_no, slot in weekday_data.items():
                for slot_type, slot_value in slot.items():
                    raw_value: float | int = cast(float | int, slot_value)
                    if slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, str):
                        raw_value = _convert_time_str_to_minutes(slot_value)
                    raw_paramset[f"{str(profile)}_{str(slot_type)}_{str(weekday)}_{slot_no}"] = (
                        raw_value
                    )
    return raw_paramset


def _add_to_schedule_data(
    schedule_data: _SCHEDULE_DICT,
    profile: ScheduleProfile,
    weekday: ScheduleWeekday,
    slot_no: int,
    slot_type: ScheduleSlotType,
    slot_value: str | float,
) -> None:
    """Add or update schedule slot."""
    if profile not in schedule_data:
        schedule_data[profile] = {}
    if weekday not in schedule_data[profile]:
        schedule_data[profile][weekday] = {}
    if slot_no not in schedule_data[profile][weekday]:
        schedule_data[profile][weekday][slot_no] = {}
    if slot_type not in schedule_data[profile][weekday][slot_no]:
        if slot_type == ScheduleSlotType.ENDTIME and isinstance(slot_value, int):
            slot_value = _convert_minutes_to_time_str(slot_value)
        schedule_data[profile][weekday][slot_no][slot_type] = slot_value


def make_simple_thermostat(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create SimpleRfThermostat entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeSimpleRfThermostat,
        device_profile=DeviceProfile.SIMPLE_RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT,
        custom_config=custom_config,
    )


def make_thermostat_group(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create RfThermostat group entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


def make_ip_thermostat(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT,
        custom_config=custom_config,
    )


def make_ip_thermostat_group(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create IPThermostat group entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT_GROUP,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ALPHA-IP-RBG": CustomConfig(make_ce_func=make_ip_thermostat),
    "BC-RT-TRX-CyG": CustomConfig(make_ce_func=make_thermostat),
    "BC-RT-TRX-CyN": CustomConfig(make_ce_func=make_thermostat),
    "BC-TC-C-WM": CustomConfig(make_ce_func=make_thermostat),
    "HM-CC-RT-DN": CustomConfig(make_ce_func=make_thermostat, channels=(4,)),
    "HM-CC-TC": CustomConfig(make_ce_func=make_simple_thermostat),
    "HM-CC-VG-1": CustomConfig(make_ce_func=make_thermostat_group),
    "HM-TC-IT-WM-W-EU": CustomConfig(make_ce_func=make_thermostat, channels=(2,)),
    "HmIP-BWTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-HEATING": CustomConfig(make_ce_func=make_ip_thermostat_group),
    "HmIP-STH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-WTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIP-eTRV": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-SCTHD": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-STH": CustomConfig(make_ce_func=make_ip_thermostat),
    "HmIPW-WTH": CustomConfig(make_ce_func=make_ip_thermostat),
    "Thermostat AA": CustomConfig(make_ce_func=make_ip_thermostat),
    "ZEL STG RM FWT": CustomConfig(make_ce_func=make_simple_thermostat),
}
hmed.ALL_DEVICES[HmPlatform.CLIMATE] = DEVICES
BLACKLISTED_DEVICES: tuple[str, ...] = ("HmIP-STHO",)
hmed.ALL_BLACKLISTED_DEVICES.append(BLACKLISTED_DEVICES)
