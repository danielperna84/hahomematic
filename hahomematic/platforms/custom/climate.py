"""
Module for entities implemented using the climate platform.

See https://www.home-assistant.io/integrations/climate/.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from enum import IntEnum, StrEnum
import logging
from typing import Any, Final

from hahomematic.const import HmPlatform, ParamsetKey
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import config_property, value_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.generic.number import HmFloat, HmInteger
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch

_LOGGER: Final = logging.getLogger(__name__)

# HA constants
_CLOSED_LEVEL: Final = 0.0
_DEFAULT_TEMPERATURE_STEP: Final = 0.5
_OFF_TEMPERATURE: Final = 4.5
_PARTY_DATE_FORMAT: Final = "%Y_%m_%d %H:%M"
_PARTY_INIT_DATE: Final = "2000_01_01 00:00"
_TEMP_CELSIUS: Final = "°C"

PRESET_MODE_PREFIX: Final = "week_program_"


class StateChangeArg(StrEnum):
    """Enum with climate state change arguments."""

    HVAC_MODE = "hvac_mode"
    PRESET_MODE = "preset_mode"
    TEMPERATURE = "temperature"


class ModeHm(StrEnum):
    """Enum with the HM modes."""

    AUTO = "AUTO-MODE"  # 0
    AWAY = "PARTY-MODE"  # 2
    BOOST = "BOOST-MODE"  # 3
    MANU = "MANU-MODE"  # 1


class ModeHmIP(IntEnum):
    """Enum with the HmIP modes."""

    AUTO = 0
    AWAY = 2
    MANU = 1


class HvacAction(StrEnum):
    """Enum with the hvac actions."""

    COOL = "cooling"
    HEAT = "heating"
    IDLE = "idle"
    OFF = "off"


class HvacMode(StrEnum):
    """Enum with the hvac modes."""

    AUTO = "auto"
    COOL = "cool"
    HEAT = "heat"
    OFF = "off"


class PresetMode(StrEnum):
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


class BaseClimateEntity(CustomEntity):
    """Base HomeMatic climate entity."""

    _platform = HmPlatform.CLIMATE

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_humidity: HmSensor = self._get_entity(field=Field.HUMIDITY, entity_type=HmSensor)
        self._e_setpoint: HmFloat = self._get_entity(field=Field.SETPOINT, entity_type=HmFloat)
        self._e_temperature: HmSensor = self._get_entity(
            field=Field.TEMPERATURE, entity_type=HmSensor
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

    @value_property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        if self._e_temperature_minimum.value is not None:
            min_temp = float(self._e_temperature_minimum.value)
        else:
            min_temp = self._e_setpoint.min

        if min_temp == _OFF_TEMPERATURE:
            return min_temp + _DEFAULT_TEMPERATURE_STEP
        return min_temp

    @value_property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        if self._e_temperature_maximum.value is not None:
            return float(self._e_temperature_maximum.value)
        return self._e_setpoint.max

    @value_property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._e_humidity.value  # type: ignore[no-any-return]

    @value_property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._e_temperature.value  # type: ignore[no-any-return]

    @value_property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._e_setpoint.value

    @config_property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return _DEFAULT_TEMPERATURE_STEP

    @value_property
    def preset_mode(self) -> PresetMode:
        """Return the current preset mode."""
        return PresetMode.NONE

    @value_property
    def preset_modes(self) -> tuple[PresetMode, ...]:
        """Return available preset modes."""
        return (PresetMode.NONE,)

    @value_property
    def hvac_action(self) -> HvacAction | None:
        """Return the hvac action."""
        return None

    @value_property
    def hvac_mode(self) -> HvacMode:
        """Return hvac operation mode."""
        return HvacMode.HEAT

    @value_property
    def hvac_modes(self) -> tuple[HvacMode, ...]:
        """Return the available hvac operation modes."""
        return (HvacMode.HEAT,)

    @config_property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return False

    @property
    def _min_or_target_temperature(self) -> float:
        """Return the min or target temperature."""
        if (temperature := self.target_temperature or self.min_temp) < self.min_temp:
            return self.min_temp
        return temperature

    @bind_collector
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

    async def set_hvac_mode(
        self, hvac_mode: HvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""

    async def set_preset_mode(
        self, preset_mode: PresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""

    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""

    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""

    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            temperature := kwargs.get(StateChangeArg.TEMPERATURE)
        ) is not None and temperature != self.target_temperature:
            return True
        if (
            hvac_mode := kwargs.get(StateChangeArg.HVAC_MODE)
        ) is not None and hvac_mode != self.hvac_mode:
            return True
        if (
            preset_mode := kwargs.get(StateChangeArg.PRESET_MODE)
        ) is not None and preset_mode != self.preset_mode:
            return True
        return super().is_state_change(**kwargs)


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
        self._e_control_mode: HmSensor = self._get_entity(
            field=Field.CONTROL_MODE, entity_type=HmSensor
        )
        self._e_valve_state: HmSensor = self._get_entity(
            field=Field.VALVE_STATE, entity_type=HmSensor
        )

    @value_property
    def hvac_action(self) -> HvacAction | None:
        """Return the hvac action."""
        if self._e_valve_state.value is None:
            return None
        if self.hvac_mode == HvacMode.OFF:
            return HvacAction.OFF
        if self._e_valve_state.value and self._e_valve_state.value > 0:
            return HvacAction.HEAT
        return HvacAction.IDLE

    @value_property
    def hvac_mode(self) -> HvacMode:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return HvacMode.OFF
        if self._e_control_mode.value == ModeHm.MANU:
            return HvacMode.HEAT
        return HvacMode.AUTO

    @value_property
    def hvac_modes(self) -> tuple[HvacMode, ...]:
        """Return the available hvac operation modes."""
        return (HvacMode.AUTO, HvacMode.HEAT, HvacMode.OFF)

    @value_property
    def preset_mode(self) -> PresetMode:
        """Return the current preset mode."""
        if self._e_control_mode.value is None:
            return PresetMode.NONE
        if self._e_control_mode.value == ModeHm.BOOST:
            return PresetMode.BOOST
        if self._e_control_mode.value == ModeHm.AWAY:
            return PresetMode.AWAY
        return PresetMode.NONE

    @value_property
    def preset_modes(self) -> tuple[PresetMode, ...]:
        """Return available preset modes."""
        return (
            PresetMode.BOOST,
            PresetMode.COMFORT,
            PresetMode.ECO,
            PresetMode.NONE,
        )

    @config_property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return True

    @bind_collector
    async def set_hvac_mode(
        self, hvac_mode: HvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""
        if not self.is_state_change(hvac_mode=hvac_mode):
            return
        if hvac_mode == HvacMode.AUTO:
            await self._e_auto_mode.send_value(value=True, collector=collector)
        elif hvac_mode == HvacMode.HEAT:
            await self._e_manu_mode.send_value(
                value=self._min_or_target_temperature, collector=collector
            )
        elif hvac_mode == HvacMode.OFF:
            await self._e_manu_mode.send_value(value=self.target_temperature, collector=collector)
            # Disable validation here to allow setting a value,
            # that is out of the validation range.
            await self.set_temperature(
                temperature=_OFF_TEMPERATURE, collector=collector, do_validate=False
            )

    @bind_collector
    async def set_preset_mode(
        self, preset_mode: PresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""
        if not self.is_state_change(preset_mode=preset_mode):
            return
        if preset_mode == PresetMode.BOOST:
            await self._e_boost_mode.send_value(value=True, collector=collector)
        elif preset_mode == PresetMode.COMFORT:
            await self._e_comfort_mode.send_value(value=True, collector=collector)
        elif preset_mode == PresetMode.ECO:
            await self._e_lowering_mode.send_value(value=True, collector=collector)

    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.set_value(
            channel_address=self._channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter="PARTY_MODE_SUBMIT",
            value=_party_mode_code(start=start, end=end, away_temperature=away_temperature),
        )

    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        start = datetime.now() - timedelta(hours=11)
        end = datetime.now() - timedelta(hours=10)

        await self._client.set_value(
            channel_address=self._channel_address,
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

    @value_property
    def hvac_action(self) -> HvacAction | None:
        """Return the hvac action."""
        if self._e_state.value is None and self._e_level.value is None:
            return None
        if self.hvac_mode == HvacMode.OFF:
            return HvacAction.OFF
        if self._e_state.value is True or (
            self._e_level.value and self._e_level.value > _CLOSED_LEVEL
        ):
            return HvacAction.HEAT if self._is_heating_mode else HvacAction.COOL
        return HvacAction.IDLE

    @value_property
    def hvac_mode(self) -> HvacMode:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= _OFF_TEMPERATURE:
            return HvacMode.OFF
        if self._e_set_point_mode.value == ModeHmIP.MANU:
            return HvacMode.HEAT if self._is_heating_mode else HvacMode.COOL
        if self._e_set_point_mode.value == ModeHmIP.AUTO:
            return HvacMode.AUTO
        return HvacMode.AUTO

    @value_property
    def hvac_modes(self) -> tuple[HvacMode, ...]:
        """Return the available hvac operation modes."""
        return (
            HvacMode.AUTO,
            HvacMode.HEAT if self._is_heating_mode else HvacMode.COOL,
            HvacMode.OFF,
        )

    @value_property
    def preset_mode(self) -> PresetMode:
        """Return the current preset mode."""
        if self._e_boost_mode.value:
            return PresetMode.BOOST
        if self._e_set_point_mode.value == ModeHmIP.AWAY:
            return PresetMode.AWAY
        if self.hvac_mode == HvacMode.AUTO:
            return self._current_profile_name if self._current_profile_name else PresetMode.NONE
        return PresetMode.NONE

    @value_property
    def preset_modes(self) -> tuple[PresetMode, ...]:
        """Return available preset modes."""
        presets = [PresetMode.BOOST, PresetMode.NONE]
        if self.hvac_mode == HvacMode.AUTO:
            presets.extend(self._profile_names)
        return tuple(presets)

    @config_property
    def supports_preset(self) -> bool:
        """Flag if climate supports preset."""
        return True

    @bind_collector
    async def set_hvac_mode(
        self, hvac_mode: HvacMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new target hvac mode."""
        if not self.is_state_change(hvac_mode=hvac_mode):
            return
        # if switching hvac_mode then disable boost_mode
        if self._e_boost_mode.value:
            await self.set_preset_mode(preset_mode=PresetMode.NONE, collector=collector)

        if hvac_mode == HvacMode.AUTO:
            await self._e_control_mode.send_value(value=ModeHmIP.AUTO, collector=collector)
        elif hvac_mode in (HvacMode.HEAT, HvacMode.COOL):
            await self._e_control_mode.send_value(value=ModeHmIP.MANU, collector=collector)
            await self.set_temperature(
                temperature=self._min_or_target_temperature, collector=collector
            )
        elif hvac_mode == HvacMode.OFF:
            await self._e_control_mode.send_value(value=ModeHmIP.MANU, collector=collector)
            await self.set_temperature(temperature=_OFF_TEMPERATURE, collector=collector)

    @bind_collector
    async def set_preset_mode(
        self, preset_mode: PresetMode, collector: CallParameterCollector | None = None
    ) -> None:
        """Set new preset mode."""
        if not self.is_state_change(preset_mode=preset_mode):
            return
        if preset_mode == PresetMode.BOOST:
            await self._e_boost_mode.send_value(value=True, collector=collector)
        elif preset_mode == PresetMode.NONE:
            await self._e_boost_mode.send_value(value=False, collector=collector)
        elif preset_mode in self._profile_names:
            if self.hvac_mode != HvacMode.AUTO:
                await self.set_hvac_mode(hvac_mode=HvacMode.AUTO, collector=collector)
                await self._e_boost_mode.send_value(value=False, collector=collector)
            if profile_idx := self._profiles.get(preset_mode):
                await self._e_active_profile.send_value(value=profile_idx, collector=collector)

    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self._client.put_paramset(
            address=self._channel_address,
            paramset_key=ParamsetKey.VALUES,
            value={
                "SET_POINT_MODE": ModeHmIP.AWAY,
                "SET_POINT_TEMPERATURE": away_temperature,
                "PARTY_TIME_START": start.strftime(_PARTY_DATE_FORMAT),
                "PARTY_TIME_END": end.strftime(_PARTY_DATE_FORMAT),
            },
        )

    async def enable_away_mode_by_duration(self, hours: int, away_temperature: float) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self._client.put_paramset(
            address=self._channel_address,
            paramset_key=ParamsetKey.VALUES,
            value={
                "SET_POINT_MODE": ModeHmIP.AWAY,
                "PARTY_TIME_START": _PARTY_INIT_DATE,
                "PARTY_TIME_END": _PARTY_INIT_DATE,
            },
        )

    @property
    def _profile_names(self) -> tuple[PresetMode, ...]:
        """Return a collection of profile names."""
        return tuple(self._profiles.keys())

    @property
    def _current_profile_name(self) -> PresetMode | None:
        """Return a profile index by name."""
        inv_profiles = {v: k for k, v in self._profiles.items()}
        if self._e_active_profile.value is not None:
            return inv_profiles.get(int(self._e_active_profile.value))
        return None

    @property
    def _profiles(self) -> Mapping[PresetMode, int]:
        """Return the profile groups."""
        profiles: dict[PresetMode, int] = {}
        if self._e_active_profile.min and self._e_active_profile.max:
            for i in range(self._e_active_profile.min, self._e_active_profile.max + 1):
                profiles[PresetMode(f"{PRESET_MODE_PREFIX}{i}")] = i

        return profiles


def make_simple_thermostat(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create SimpleRfThermostat entities."""
    return hmed.make_custom_entity(
        device=device,
        entity_class=CeSimpleRfThermostat,
        device_profile=DeviceProfile.SIMPLE_RF_THERMOSTAT,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_thermostat(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create RfThermostat entities."""
    return hmed.make_custom_entity(
        device=device,
        entity_class=CeRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_thermostat_group(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create RfThermostat group entities."""
    return hmed.make_custom_entity(
        device=device,
        entity_class=CeRfThermostat,
        device_profile=DeviceProfile.RF_THERMOSTAT_GROUP,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_ip_thermostat(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create IPThermostat entities."""
    return hmed.make_custom_entity(
        device=device,
        entity_class=CeIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT,
        group_base_channels=group_base_channels,
        extended=extended,
    )


def make_ip_thermostat_group(
    device: hmd.HmDevice,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[CustomEntity, ...]:
    """Create IPThermostat group entities."""
    return hmed.make_custom_entity(
        device=device,
        entity_class=CeIpThermostat,
        device_profile=DeviceProfile.IP_THERMOSTAT_GROUP,
        group_base_channels=group_base_channels,
        extended=extended,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "ALPHA-IP-RBG": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "BC-RT-TRX-CyG": CustomConfig(make_ce_func=make_thermostat, channels=(1,)),
    "BC-RT-TRX-CyN": CustomConfig(make_ce_func=make_thermostat, channels=(1,)),
    "BC-TC-C-WM": CustomConfig(make_ce_func=make_thermostat, channels=(1,)),
    "HM-CC-RT-DN": CustomConfig(make_ce_func=make_thermostat, channels=(4,)),
    "HM-CC-TC": CustomConfig(make_ce_func=make_simple_thermostat, channels=(1,)),
    "HM-CC-VG-1": CustomConfig(make_ce_func=make_thermostat_group, channels=(1,)),
    "HM-TC-IT-WM-W-EU": CustomConfig(make_ce_func=make_thermostat, channels=(2,)),
    "HmIP-BWTH": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIP-HEATING": CustomConfig(make_ce_func=make_ip_thermostat_group, channels=(1,)),
    "HmIP-STH": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIP-WTH": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIP-eTRV": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIPW-SCTHD": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIPW-STH": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "HmIPW-WTH": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "Thermostat AA": CustomConfig(make_ce_func=make_ip_thermostat, channels=(1,)),
    "ZEL STG RM FWT": CustomConfig(make_ce_func=make_simple_thermostat, channels=(1,)),
}
hmed.ALL_DEVICES.append(DEVICES)
BLACKLISTED_DEVICES: tuple[str, ...] = ("HmIP-STHO",)
hmed.ALL_BLACKLISTED_DEVICES.append(BLACKLISTED_DEVICES)
