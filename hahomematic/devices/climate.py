"""Code to create the required entities for thermostat devices."""
from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_ACTIVE_PROFILE,
    FIELD_AUTO_MODE,
    FIELD_BOOST_MODE,
    FIELD_COMFORT_MODE,
    FIELD_CONTROL_MODE,
    FIELD_HEATING_COOLING,
    FIELD_HUMIDITY,
    FIELD_LOWERING_MODE,
    FIELD_MANU_MODE,
    FIELD_PARTY_MODE,
    FIELD_SET_POINT_MODE,
    FIELD_SETPOINT,
    FIELD_TEMPERATURE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.number import HmFloat, HmInteger
from hahomematic.platforms.select import HmSelect
from hahomematic.platforms.switch import HmSwitch

_LOGGER = logging.getLogger(__name__)

HM_MODE_AUTO = "AUTO-MODE"
HM_MODE_MANU = "MANU-MODE"
HM_MODE_AWAY = "PARTY-MODE"
HM_MODE_BOOST = "BOOST-MODE"
HMIP_SET_POINT_MODE_AUTO = 0
HMIP_SET_POINT_MODE_MANU = 1
HMIP_SET_POINT_MODE_AWAY = 2

ATTR_TEMPERATURE = "temperature"
HVAC_MODE_OFF = "off"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_AUTO = "auto"
HVAC_MODE_COOL = "cool"
PARTY_INIT_DATE = "2000_01_01 00:00"
PARTY_DATE_FORMAT = "%Y_%m_%d %H:%M"
PRESET_NONE = "none"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
TEMP_CELSIUS = "°C"
SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_PRESET_MODE = 16

HM_MIN_VALUE = 4.5
HM_MAX_VALUE = 30.5


class BaseClimateEntity(CustomEntity):
    """Base HomeMatic climate entity."""

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
            platform=HmPlatform.CLIMATE,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "ClimateEntity.__init__(%s, %s, %s)",
            self._device.interface_id,
            device_address,
            unique_id,
        )

    @property
    def _humidity(self) -> int | None:
        """Return the humidity of the device."""
        return self._get_entity_value(field_name=FIELD_HUMIDITY)

    @property
    def _e_setpoint(self) -> HmFloat:
        """Return the setpoint entity of the device."""
        return self._get_entity(field_name=FIELD_SETPOINT, entity_type=HmFloat)

    @property
    def _temperature(self) -> float | None:
        """Return the temperature of the device."""
        return self._get_entity_value(field_name=FIELD_TEMPERATURE)

    @property
    def temperature_unit(self) -> str:
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._e_setpoint.min

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._e_setpoint.max

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self._humidity

    @property
    def current_temperature(self) -> float | None:
        """Return current temperature."""
        return self._temperature

    @property
    def target_temperature(self) -> float | None:
        """Return target temperature."""
        return self._e_setpoint.value

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return [PRESET_NONE]

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO]

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    async def set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        await self._e_setpoint.send_value(float(temperature))

    # pylint: disable=no-self-use
    async def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        return None

    # pylint: disable=no-self-use
    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        return None

    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        return None

    async def enable_away_mode_by_duration(
        self, hours: int, away_temperature: float
    ) -> None:
        """Enable the away mode by duration on thermostat."""
        return None

    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        return None


class CeSimpleRfThermostat(BaseClimateEntity):
    """Simple classic HomeMatic thermostat HM-CC-TC."""


class CeRfThermostat(BaseClimateEntity):
    """Classic HomeMatic thermostat like HM-CC-RT-DN."""

    @property
    def _e_boost_mode(self) -> HmSwitch:
        """Return the boost_mode entity of the device."""
        return self._get_entity(field_name=FIELD_BOOST_MODE, entity_type=HmSwitch)

    @property
    def _e_auto_mode(self) -> HmAction:
        """Return the auto_mode entity of the device."""
        return self._get_entity(field_name=FIELD_AUTO_MODE, entity_type=HmAction)

    @property
    def _e_manu_mode(self) -> HmAction:
        """Return the manu_mode entity of the device."""
        return self._get_entity(field_name=FIELD_MANU_MODE, entity_type=HmAction)

    @property
    def _e_comfort_mode(self) -> HmAction:
        """Return the comfort_mode entity of the device."""
        return self._get_entity(field_name=FIELD_COMFORT_MODE, entity_type=HmAction)

    @property
    def _e_lowering_mode(self) -> HmAction:
        """Return the lowering_mode entity of the device."""
        return self._get_entity(field_name=FIELD_LOWERING_MODE, entity_type=HmAction)

    @property
    def _control_mode(self) -> str | None:
        """Return the control_mode of the device."""
        return self._get_entity_value(field_name=FIELD_CONTROL_MODE)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self._control_mode == HM_MODE_MANU:
            return HVAC_MODE_HEAT
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if self._control_mode is None:
            return PRESET_NONE
        if self._control_mode == HM_MODE_BOOST:
            return PRESET_BOOST
        if self._control_mode == HM_MODE_AWAY:
            return PRESET_AWAY
        # This mode (PRESET_AWY) generally is available, but
        # we can't set it from the Home Assistant UI natively.
        # We could create 2 input_datetime entities and reference them
        # and number.xxx_4_party_temperature when setting the preset.
        # More info on format: https://homematic-forum.de/forum/viewtopic.php?t=34673#p330200
        # Example-payload (21.5° from 2021-03-16T01:00-2021-03-17T23:00):
        # "21.5,60,16,3,21,1380,17,3,21"
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        return [PRESET_BOOST, PRESET_COMFORT, PRESET_ECO, PRESET_NONE]

    async def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self._e_auto_mode.send_value(True)
        elif hvac_mode == HVAC_MODE_HEAT:
            await self._e_manu_mode.send_value(self.current_temperature)
        elif hvac_mode == HVAC_MODE_OFF:
            await self.set_temperature(temperature=self.min_temp)
        # if switching hvac_mode then disable boost_mode
        if self._e_boost_mode.value:
            await self.set_preset_mode(PRESET_NONE)

    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self._e_boost_mode.send_value(True)
        elif preset_mode == PRESET_COMFORT:
            await self._e_comfort_mode.send_value(True)
        elif preset_mode == PRESET_ECO:
            await self._e_lowering_mode.send_value(True)
        elif preset_mode == PRESET_NONE:
            await self._e_boost_mode.send_value(False)


class CeIpThermostat(BaseClimateEntity):
    """homematic IP thermostat like HmIP-eTRV-B."""

    @property
    def _e_active_profile(self) -> HmInteger:
        """Return the active_profile entity of the device."""
        return self._get_entity(field_name=FIELD_ACTIVE_PROFILE, entity_type=HmInteger)

    @property
    def _e_boost_mode(self) -> HmSwitch:
        """Return the boost_mode entity of the device."""
        return self._get_entity(field_name=FIELD_BOOST_MODE, entity_type=HmSwitch)

    @property
    def _e_control_mode(self) -> HmAction:
        """Return the control_mode entity of the device."""
        return self._get_entity(field_name=FIELD_CONTROL_MODE, entity_type=HmAction)

    @property
    def _is_heating(self) -> bool | None:
        if heating_cooling := self._get_entity(
            field_name=FIELD_HEATING_COOLING, entity_type=HmSelect
        ):
            if heating_cooling.value:
                return str(heating_cooling.value) == "HEATING"
        return True

    @property
    def _party_mode(self) -> bool | None:
        """Return the party_mode of the device."""
        return self._get_entity_value(field_name=FIELD_PARTY_MODE)

    @property
    def _e_set_point_mode(self) -> HmInteger:
        """Return the set_point_mode entity of the device."""
        return self._get_entity(field_name=FIELD_SET_POINT_MODE, entity_type=HmInteger)

    @property
    def supported_features(self) -> int:
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def hvac_mode(self) -> str:
        """Return hvac operation mode."""
        if self.target_temperature and self.target_temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self._e_set_point_mode.value == HMIP_SET_POINT_MODE_MANU:
            return HVAC_MODE_HEAT if self._is_heating else HVAC_MODE_COOL
        if self._e_set_point_mode.value == HMIP_SET_POINT_MODE_AUTO:
            return HVAC_MODE_AUTO
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self) -> list[str]:
        """Return the list of available hvac operation modes."""
        return [
            HVAC_MODE_AUTO,
            HVAC_MODE_HEAT if self._is_heating else HVAC_MODE_COOL,
            HVAC_MODE_OFF,
        ]

    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        if self._e_boost_mode.value:
            return PRESET_BOOST
        if self._e_set_point_mode.value == HMIP_SET_POINT_MODE_AWAY:
            return PRESET_AWAY
        if self.hvac_mode == HVAC_MODE_AUTO:
            return (
                self._current_profile_name
                if self._current_profile_name
                else PRESET_NONE
            )
        return PRESET_NONE

    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        presets = [PRESET_BOOST, PRESET_NONE]
        if self.hvac_mode == HVAC_MODE_AUTO:
            presets.extend(self._profile_names)
        return presets

    async def set_hvac_mode(self, hvac_mode: str) -> None:
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self._e_control_mode.send_value(HMIP_SET_POINT_MODE_AUTO)
        elif hvac_mode in (HVAC_MODE_HEAT, HVAC_MODE_COOL):
            await self._e_control_mode.send_value(HMIP_SET_POINT_MODE_MANU)
        elif hvac_mode == HVAC_MODE_OFF:
            await self._e_control_mode.send_value(HMIP_SET_POINT_MODE_MANU)
            await self.set_temperature(temperature=self.min_temp)
        # if switching hvac_mode then disable boost_mode
        if self._e_boost_mode.value:
            await self.set_preset_mode(PRESET_NONE)

    async def set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self._e_boost_mode.send_value(True)
        if preset_mode == PRESET_NONE:
            await self._e_boost_mode.send_value(False)

        if preset_mode in self._profile_names:
            if self.hvac_mode != HVAC_MODE_AUTO:
                await self.set_hvac_mode(HVAC_MODE_AUTO)
            profile_idx = self._profiles.get(preset_mode)
            await self._e_boost_mode.send_value(False)
            if profile_idx:
                await self._e_active_profile.send_value(profile_idx)

    async def enable_away_mode_by_calendar(
        self, start: datetime, end: datetime, away_temperature: float
    ) -> None:
        """Enable the away mode by calendar on thermostat."""
        await self.put_paramset(
            paramset="VALUES",
            value={
                "CONTROL_MODE": HMIP_SET_POINT_MODE_AWAY,
                "PARTY_TIME_END": end.strftime(PARTY_DATE_FORMAT),
                "PARTY_TIME_START": start.strftime(PARTY_DATE_FORMAT),
            },
        )
        await self.put_paramset(
            paramset="VALUES",
            value={
                "SET_POINT_TEMPERATURE": away_temperature,
            },
        )

    async def enable_away_mode_by_duration(
        self, hours: int, away_temperature: float
    ) -> None:
        """Enable the away mode by duration on thermostat."""
        start = datetime.now() - timedelta(minutes=10)
        end = datetime.now() + timedelta(hours=hours)
        await self.enable_away_mode_by_calendar(
            start=start, end=end, away_temperature=away_temperature
        )

    async def disable_away_mode(self) -> None:
        """Disable the away mode on thermostat."""
        await self.put_paramset(
            paramset="VALUES",
            value={
                "CONTROL_MODE": HMIP_SET_POINT_MODE_AUTO,
                "PARTY_TIME_START": PARTY_INIT_DATE,
                "PARTY_TIME_END": PARTY_INIT_DATE,
            },
        )

    @property
    def _profile_names(self) -> list[str]:
        """Return a collection of profile names."""
        return list(self._profiles.keys())

    @property
    def _current_profile_name(self) -> str | None:
        """Return a profile index by name."""
        inv_profiles: dict[int, str] = {v: k for k, v in self._profiles.items()}
        if self._e_active_profile.value:
            return inv_profiles.get(int(self._e_active_profile.value))
        return None

    @property
    def _profiles(self) -> dict[str, int]:
        """Return the profile groups."""
        profiles: dict[str, int] = {}
        for i in range(self._e_active_profile.min, self._e_active_profile.max + 1):
            profiles[f"Profile {i}"] = i

        return profiles


def make_simple_thermostat(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates SimpleRfThermostat entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeSimpleRfThermostat,
        device_enum=EntityDefinition.SIMPLE_RF_THERMOSTAT,
        group_base_channels=group_base_channels,
    )


def make_thermostat(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates RfThermostat entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeRfThermostat,
        device_enum=EntityDefinition.RF_THERMOSTAT,
        group_base_channels=group_base_channels,
    )


def make_thermostat_group(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates RfThermostat group entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeRfThermostat,
        device_enum=EntityDefinition.RF_THERMOSTAT_GROUP,
        group_base_channels=group_base_channels,
    )


def make_ip_thermostat(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates IPThermostat entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeIpThermostat,
        device_enum=EntityDefinition.IP_THERMOSTAT,
        group_base_channels=group_base_channels,
    )


def make_ip_thermostat_group(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates IPThermostat group entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeIpThermostat,
        device_enum=EntityDefinition.IP_THERMOSTAT_GROUP,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "BC-RT-TRX-CyG*": (make_thermostat, [1]),
    "BC-RT-TRX-CyN*": (make_thermostat, [1]),
    "BC-TC-C-WM*": (make_thermostat, [1]),
    "HM-CC-RT-DN*": (make_thermostat, [4]),
    "HM-CC-TC": (make_simple_thermostat, [1]),
    "HM-CC-VG-1": (make_thermostat_group, [1]),
    "HM-TC-IT-WM-W-EU": (make_thermostat, [2]),
    "HmIP-BWTH*": (make_ip_thermostat, [1]),
    "HmIP-eTRV*": (make_ip_thermostat, [1]),
    "HmIP-HEATING": (make_ip_thermostat_group, [1]),
    "HmIP-STHD": (make_ip_thermostat, [1]),
    "HmIP-WTH*": (make_ip_thermostat, [1]),
    "HmIPW-STH*": (make_ip_thermostat, [1]),
    "HmIPW-WTH*": (make_ip_thermostat, [1]),
    "Thermostat AA*": (make_ip_thermostat, [1]),
    "ZEL STG RM FWT": (make_simple_thermostat, [1]),
}
