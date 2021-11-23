"""Code to create the required entities for thermostat devices."""

import logging

from hahomematic.const import ATTR_HM_MAX, ATTR_HM_MIN, HA_PLATFORM_CLIMATE
from hahomematic.devices.device_description import (
    FIELD_AUTO_MODE,
    FIELD_BOOST_MODE,
    FIELD_COMFORT_MODE,
    FIELD_CONTROL_MODE,
    FIELD_HUMIDITY,
    FIELD_LOWERING_MODE,
    FIELD_MANU_MODE,
    FIELD_PARTY_MODE,
    FIELD_SET_POINT_MODE,
    FIELD_SETPOINT,
    FIELD_TEMPERATURE,
    Devices,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

_LOGGER = logging.getLogger(__name__)

HM_MODE_AUTO = 0
HM_MODE_MANU = 1
HM_MODE_AWAY = 2
HM_MODE_BOOST = 3
HMIP_SET_POINT_MODE_AUTO = 0
HMIP_SET_POINT_MODE_MANU = 1
HMIP_SET_POINT_MODE_AWAY = 2

ATTR_TEMPERATURE = "temperature"
HVAC_MODE_OFF = "off"
HVAC_MODE_HEAT = "heat"
HVAC_MODE_AUTO = "auto"
PRESET_NONE = "none"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
TEMP_CELSIUS = "°C"
SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_PRESET_MODE = 16


class SimpleThermostat(CustomEntity):
    """Simple classic HomeMatic thermostat HM-CC-TC."""

    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_CLIMATE,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "SimpleThermostat.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _humidity(self) -> int:
        """Return the humidity of the device."""
        return self._get_entity_value(FIELD_HUMIDITY)

    @property
    def _temperature(self) -> float:
        """Return the temperature of the device."""
        return self._get_entity_value(FIELD_TEMPERATURE)

    @property
    def _setpoint(self) -> float:
        """Return the setpoint of the device."""
        return self._get_entity_value(FIELD_SETPOINT)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MIN.lower(), 4.5)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MAX.lower(), 30.5)

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO]

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._humidity

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._temperature

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return self._setpoint

    async def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        await self._send_value(FIELD_SETPOINT, float(temperature))


class Thermostat(CustomEntity):
    """Classic HomeMatic thermostat like HM-CC-RT-DN."""

    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_CLIMATE,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "Thermostat.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _humidity(self) -> int:
        """Return the humidity of the device."""
        return self._get_entity_value(FIELD_HUMIDITY)

    @property
    def _temperature(self) -> float:
        """Return the temperature of the device."""
        return self._get_entity_value(FIELD_TEMPERATURE)

    @property
    def _setpoint(self) -> float:
        """Return the setpoint of the device."""
        return self._get_entity_value(FIELD_SETPOINT)

    @property
    def _control_mode(self):
        """Return the control_mode of the device."""
        return self._get_entity_value(FIELD_CONTROL_MODE)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MIN.lower(), 4.5)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MAX.lower(), 30.5)

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        if self._temperature and self._temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self._control_mode == HM_MODE_MANU:
            return HVAC_MODE_HEAT
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._control_mode is None:
            return PRESET_NONE
        if self._control_mode == HM_MODE_BOOST:
            return PRESET_BOOST
        # elif control_mode == HM_MODE_AWAY:
        #     return PRESET_AWAY
        # This mode (PRESET_AWY) generally is available, but we're hiding it because
        # we can't set it from the Home Assistant UI natively.
        # We could create 2 input_datetime entities and reference them
        # and number.xxx_4_party_temperature when setting the preset.
        # More info on format: https://homematic-forum.de/forum/viewtopic.php?t=34673#p330200
        # Example-payload (21.5° from 2021-03-16T01:00-2021-03-17T23:00):
        # "21.5,60,16,3,21,1380,17,3,21"
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_BOOST, PRESET_COMFORT, PRESET_ECO]

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._humidity

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._temperature

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return self._setpoint

    async def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        await self._send_value(FIELD_SETPOINT, float(temperature))

    async def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self._send_value(FIELD_AUTO_MODE, True)
        elif hvac_mode == HVAC_MODE_HEAT:
            await self._send_value(FIELD_MANU_MODE, self.max_temp)
        elif hvac_mode == HVAC_MODE_OFF:
            await self.set_temperature(temperature=self.min_temp)

    async def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self._send_value(FIELD_BOOST_MODE, True)
        elif preset_mode == PRESET_COMFORT:
            await self._send_value(FIELD_COMFORT_MODE, True)
        elif preset_mode == PRESET_ECO:
            await self._send_value(FIELD_LOWERING_MODE, True)


class IPThermostat(CustomEntity):
    """homematic IP thermostat like HmIP-eTRV-B."""

    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
            platform=HA_PLATFORM_CLIMATE,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "IPThermostat.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    def _humidity(self) -> int:
        return self._get_entity_value(FIELD_HUMIDITY)

    @property
    def _temperature(self) -> float:
        return self._get_entity_value(FIELD_TEMPERATURE)

    @property
    def _setpoint(self) -> float:
        return self._get_entity_value(FIELD_SETPOINT)

    @property
    def _set_point_mode(self):
        return self._get_entity_value(FIELD_SET_POINT_MODE)

    @property
    def _control_mode(self):
        return self._get_entity_value(FIELD_CONTROL_MODE)

    @property
    def _boost_mode(self):
        return self._get_entity_value(FIELD_BOOST_MODE)

    @property
    def _party_mode(self):
        return self._get_entity_value(FIELD_PARTY_MODE)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self) -> float:
        """Return the minimum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MIN.lower(), 4.5)

    @property
    def max_temp(self) -> float:
        """Return the maximum temperature."""
        return self._get_entity_attribute(FIELD_SETPOINT, ATTR_HM_MAX.lower(), 30.5)

    @property
    def target_temperature_step(self) -> float:
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        if self._temperature and self._temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self._set_point_mode == HMIP_SET_POINT_MODE_MANU:
            return HVAC_MODE_HEAT
        if self._set_point_mode == HMIP_SET_POINT_MODE_AUTO:
            return HVAC_MODE_AUTO
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self._boost_mode:
            return PRESET_BOOST
        # This mode (PRESET_AWAY) generally is available, but we're hiding it because
        # we can't set it from the Home Assistant UI natively.
        # if self.set_point_mode == HMIP_SET_POINT_MODE_AWAY:
        #     return PRESET_AWAY
        return PRESET_NONE

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return [PRESET_BOOST]

    @property
    def current_humidity(self) -> int:
        """Return the current humidity."""
        return self._humidity

    @property
    def current_temperature(self) -> float:
        """Return current temperature."""
        return self._temperature

    @property
    def target_temperature(self) -> float:
        """Return target temperature."""
        return self._setpoint

    async def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        await self._send_value(FIELD_SETPOINT, float(temperature))

    async def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            await self._send_value(FIELD_CONTROL_MODE, HMIP_SET_POINT_MODE_AUTO)
        elif hvac_mode == HVAC_MODE_HEAT:
            await self._send_value(FIELD_CONTROL_MODE, HMIP_SET_POINT_MODE_MANU)
        elif hvac_mode == HVAC_MODE_OFF:
            await self._send_value(FIELD_CONTROL_MODE, HMIP_SET_POINT_MODE_MANU)
            await self.set_temperature(temperature=self.min_temp)

    async def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            await self._send_value(FIELD_BOOST_MODE, True)


def make_simple_thermostat(device, address, group_base_channels: [int]):
    """Creates SimpleThermostat entities."""
    return make_custom_entity(
        device,
        address,
        SimpleThermostat,
        Devices.SIMPLE_RF_THERMOSTAT,
        group_base_channels,
    )


def make_thermostat(device, address, group_base_channels: [int]):
    """Creates Thermostat entities."""
    return make_custom_entity(
        device, address, Thermostat, Devices.RF_THERMOSTAT, group_base_channels
    )


def make_ip_thermostat(device, address, group_base_channels: [int]):
    """Creates IPThermostat entities."""
    return make_custom_entity(
        device, address, IPThermostat, Devices.IP_THERMOSTAT, group_base_channels
    )


DEVICES = {
    "BC-RT-TRX-CyG*": (make_thermostat, []),
    "BC-RT-TRX-CyN*": (make_thermostat, []),
    "BC-TC-C-WM*": (make_thermostat, []),
    "HM-CC-RT-DN*": (make_thermostat, []),
    "HM-CC-TC": (make_simple_thermostat, []),
    "HM-CC-VG-1": (make_thermostat, []),
    "HM-TC-IT-WM-W-EU": (make_thermostat, []),
    "HmIP-BWTH*": (make_ip_thermostat, []),
    "HmIP-eTRV*": (make_ip_thermostat, []),
    "HmIP-HEATING": (make_ip_thermostat, []),
    "HmIP-STHD": (make_ip_thermostat, []),
    "HmIP-WTH*": (make_ip_thermostat, []),
    "HmIPW-STHD": (make_ip_thermostat, []),
    "HmIPW-WTH*": (make_ip_thermostat, []),
    "Thermostat AA*": (make_ip_thermostat, []),
    "ZEL STG RM FWT": (make_simple_thermostat, []),
}
