# pylint: disable=line-too-long
"""
Code to create the required entities for thermostat devices.
"""

import logging

from hahomematic import data, config
from hahomematic.platforms.climate import climate
from hahomematic.helpers import generate_unique_id
# from hahomematic.const import (
#     PARAMSET_MASTER
# )

LOG = logging.getLogger(__name__)

ENTITY_ACTUAL_TEMPERATURE = 'ENTITY_ACTUAL_TEMPERATURE'
ENTITY_SET_TEMPERATURE = 'ENTITY_SET_TEMPERATURE'
ENTITY_CONTROL_MODE = 'ENTITY_CONTROL_MODE'
ENTITY_HUMIDITY = 'ENTITY_HUMIDITY'
ENTITY_AUTO_MODE = 'ENTITY_AUTO_MODE'
ENTITY_MANU_MODE = 'ENTITY_MANU_MODE'
ENTITY_BOOST_MODE = 'ENTITY_BOOST_MODE'
ENTITY_COMFORT_MODE = 'ENTITY_COMFORT_MODE'
ENTITY_LOWERING_MODE = 'ENTITY_LOWERING_MODE'

HM_MODE_AUTO = 0
HM_MODE_MANU = 1
HM_MODE_AWAY = 2
HM_MODE_BOOST = 3
HM_MODE_AUTO_ENUM = 'AUTO-MODE'
HM_MODE_MANU_ENUM = 'MANU-MODE'
HM_MODE_AWAY_ENUM = 'PARTY-MODE'
HM_MODE_BOOST_ENUM = 'BOOST-MODE'
HM_MODE_ENUM_MAP = {
    HM_MODE_AUTO_ENUM: HM_MODE_AUTO,
    HM_MODE_MANU_ENUM: HM_MODE_MANU,
    HM_MODE_AWAY_ENUM: HM_MODE_AWAY,
    HM_MODE_BOOST_ENUM: HM_MODE_BOOST,
}

ATTR_TEMPERATURE = "temperature"
HVAC_MODE_OFF = 'off'
HVAC_MODE_HEAT = 'heat'
HVAC_MODE_AUTO = 'auto'
PRESET_NONE = "none"
PRESET_AWAY = "away"
PRESET_BOOST = "boost"
PRESET_COMFORT = "comfort"
PRESET_ECO = "eco"
TEMP_CELSIUS = "°C"
SUPPORT_TARGET_TEMPERATURE = 1
SUPPORT_PRESET_MODE = 16
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

# pylint: disable=too-many-instance-attributes
class SimpleThermostat(climate):
    """
    Simple classic HomeMatic thermostat HM-CC-TC.
    This implementation reuses the existing entities associated
    to this device.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, address, entity_id, unique_id, entities):
        LOG.debug("SimpleThermostat.__init__(%s, %s, %s, %s)",
                  interface_id, address, entity_id, unique_id)
        self.interface_id = interface_id
        self.address = address
        self.unique_id = unique_id
        self.entity_id = entity_id
        self.name = data.NAMES.get(
            self.interface_id, {}).get(self.address, self.entity_id)
        self.ha_device = data.HA_DEVICES[self.address]
        self.channels = list(data.DEVICES[self.interface_id][self.address].keys())
        # Subscribe for all events of this device
        if not self.address in data.EVENT_SUBSCRIPTIONS_DEVICE:
            data.EVENT_SUBSCRIPTIONS_DEVICE[self.address] = []
        data.EVENT_SUBSCRIPTIONS_DEVICE[self.address].append(self.event)
        self.update_callback = None
        if callable(config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = config.CALLBACK_ENTITY_UPDATE
        self._entity_actual_temperature = entities.get(ENTITY_ACTUAL_TEMPERATURE)
        self._entity_set_temperature = entities.get(ENTITY_SET_TEMPERATURE)
        self._entity_humidity = entities.get(ENTITY_HUMIDITY)

    def event(self, interface_id, address, value_key, value):
        """
        Handle event for this device.
        """
        if interface_id == self.interface_id:
            LOG.debug("SimpleThermostat.event(%s, %s, %s, %s)",
                      interface_id, address, value_key, value)
            self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("SimpleThermostat.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.entity_id)

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return data.ENTITIES[self._entity_set_temperature].min

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return data.ENTITIES[self._entity_set_temperature].max

    @property
    def target_temperature_step(self):
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
    def current_humidity(self):
        """Return the current humidity."""
        if self._entity_humidity is None:
            return None
        return data.ENTITIES[self._entity_humidity].STATE

    @property
    def current_temperature(self):
        """Return current temperature."""
        return data.ENTITIES[self._entity_actual_temperature].STATE

    @property
    def target_temperature(self):
        """Return target temperature."""
        return data.ENTITIES[self._entity_set_temperature].STATE

    # pylint: disable=inconsistent-return-statements
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        data.ENTITIES[self._entity_set_temperature].STATE = float(temperature)

class Thermostat(climate):
    """
    Classic HomeMatic thermostat like HM-CC-RT-DN.
    This implementation reuses the existing entities associated
    to this device.
    """
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, address, entity_id, unique_id, entities):
        LOG.debug("Thermostat.__init__(%s, %s, %s, %s)",
                  interface_id, address, entity_id, unique_id)
        self.interface_id = interface_id
        self.address = address
        self.unique_id = unique_id
        self.entity_id = entity_id
        self.name = data.NAMES.get(
            self.interface_id, {}).get(self.address, self.entity_id)
        self.ha_device = data.HA_DEVICES[self.address]
        self.channels = list(data.DEVICES[self.interface_id][self.address].keys())
        # Subscribe for all events of this device
        if not self.address in data.EVENT_SUBSCRIPTIONS_DEVICE:
            data.EVENT_SUBSCRIPTIONS_DEVICE[self.address] = []
        data.EVENT_SUBSCRIPTIONS_DEVICE[self.address].append(self.event)
        self.update_callback = None
        if callable(config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = config.CALLBACK_ENTITY_UPDATE
        self._entity_actual_temperature = entities.get(ENTITY_ACTUAL_TEMPERATURE)
        self._entity_set_temperature = entities.get(ENTITY_SET_TEMPERATURE)
        self._entity_control_mode = entities.get(ENTITY_CONTROL_MODE)
        self._entity_humidity = entities.get(ENTITY_HUMIDITY)
        self._entity_auto_mode = entities.get(ENTITY_AUTO_MODE)
        self._entity_manu_mode = entities.get(ENTITY_MANU_MODE)
        self._entity_boost_mode = entities.get(ENTITY_BOOST_MODE)
        self._entity_comfort_mode = entities.get(ENTITY_COMFORT_MODE)
        self._entity_lowering_mode = entities.get(ENTITY_LOWERING_MODE)

    def event(self, interface_id, address, value_key, value):
        """
        Handle event for this device.
        """
        if interface_id == self.interface_id:
            LOG.debug("Thermostat.event(%s, %s, %s, %s)",
                      interface_id, address, value_key, value)
            self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("Thermostat.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.entity_id)

    @property
    def _hm_control_mode(self):
        """
        Return current control mode. Will always be an integer.
        """
        # pylint: disable=protected-access
        return data.ENTITIES[self._entity_control_mode]._state

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def temperature_unit(self):
        """Return temperature unit."""
        return TEMP_CELSIUS

    @property
    def min_temp(self):
        """Return the minimum temperature."""
        return data.ENTITIES[self._entity_set_temperature].min

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return data.ENTITIES[self._entity_set_temperature].max

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        if data.ENTITIES[self._entity_set_temperature].STATE <= self.min_temp:
            return HVAC_MODE_OFF
        if self._hm_control_mode == HM_MODE_MANU:
            return HVAC_MODE_HEAT
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        control_mode = self._hm_control_mode
        if control_mode is None:
            return PRESET_NONE
        if control_mode == HM_MODE_BOOST:
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
    def current_humidity(self):
        """Return the current humidity."""
        if self._entity_humidity is None:
            return None
        return data.ENTITIES[self._entity_humidity].STATE

    @property
    def current_temperature(self):
        """Return current temperature."""
        return data.ENTITIES[self._entity_actual_temperature].STATE

    @property
    def target_temperature(self):
        """Return target temperature."""
        return data.ENTITIES[self._entity_set_temperature].STATE

    # pylint: disable=inconsistent-return-statements
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        data.ENTITIES[self._entity_set_temperature].STATE = float(temperature)

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            data.ENTITIES[self._entity_auto_mode].STATE = True
        elif hvac_mode == HVAC_MODE_HEAT:
            target_temp = self.target_temperature
            if target_temp <= self.min_temp:
                target_temp = self.min_temp + self.target_temperature_step
            data.ENTITIES[self._entity_manu_mode].STATE = float(target_temp)
        elif hvac_mode == HVAC_MODE_OFF:
            self.set_temperature(temperature=self.min_temp)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            data.ENTITIES[self._entity_boost_mode].STATE = True
        elif preset_mode == PRESET_COMFORT:
            data.ENTITIES[self._entity_comfort_mode].STATE = True
        elif preset_mode == PRESET_ECO:
            data.ENTITIES[self._entity_lowering_mode].STATE = True

def make_simple_thermostat(interface_id, address):
    """
    Helper to create SimpleThermostat entities.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_simple_thermostat: Skipping %s (already exists)", entity_id)
    device_entities = {
        ENTITY_ACTUAL_TEMPERATURE: f"sensor.{unique_id}_1_temperature",
        ENTITY_HUMIDITY: f"sensor.{unique_id}_1_humidity",
        ENTITY_SET_TEMPERATURE: f"number.{unique_id}_2_setpoint",
    }
    data.ENTITIES[entity_id] = SimpleThermostat(interface_id, address, entity_id, unique_id, device_entities)
    data.HA_DEVICES[address].entities.add(entity_id)

def make_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_thermostat: Skipping %s (already exists)", entity_id)
    device_entities = {
        ENTITY_ACTUAL_TEMPERATURE: f"sensor.{unique_id}_4_actual_temperature",
        ENTITY_SET_TEMPERATURE: f"number.{unique_id}_4_set_temperature",
        ENTITY_CONTROL_MODE: f"sensor.{unique_id}_4_control_mode",
        ENTITY_AUTO_MODE: f"switch.{unique_id}_4_auto_mode",
        ENTITY_MANU_MODE: f"number.{unique_id}_4_manu_mode",
        ENTITY_BOOST_MODE: f"switch.{unique_id}_4_boost_mode",
        ENTITY_COMFORT_MODE: f"switch.{unique_id}_4_comfort_mode",
        ENTITY_LOWERING_MODE: f"switch.{unique_id}_4_lowering_mode",
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, device_entities)
    data.HA_DEVICES[address].entities.add(entity_id)

def make_wall_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities for wall-thermostats.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_wall_thermostat: Skipping %s (already exists)", entity_id)
    device_entities = {
        ENTITY_ACTUAL_TEMPERATURE: f"sensor.{unique_id}_2_actual_temperature",
        ENTITY_SET_TEMPERATURE: f"number.{unique_id}_2_set_temperature",
        ENTITY_CONTROL_MODE: f"sensor.{unique_id}_2_control_mode",
        ENTITY_AUTO_MODE: f"switch.{unique_id}_2_auto_mode",
        ENTITY_MANU_MODE: f"number.{unique_id}_2_manu_mode",
        ENTITY_BOOST_MODE: f"switch.{unique_id}_2_boost_mode",
        ENTITY_COMFORT_MODE: f"switch.{unique_id}_2_comfort_mode",
        ENTITY_LOWERING_MODE: f"switch.{unique_id}_2_lowering_mode",
        ENTITY_HUMIDITY: f"sensor.{unique_id}_2_humidity",
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, device_entities)
    data.HA_DEVICES[address].entities.add(entity_id)

def make_group_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities for heating groups.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_group_thermostat: Skipping %s (already exists)", entity_id)
    device_entities = {
        ENTITY_ACTUAL_TEMPERATURE: f"sensor.{unique_id}_1_actual_temperature",
        ENTITY_SET_TEMPERATURE: f"number.{unique_id}_1_set_temperature",
        ENTITY_CONTROL_MODE: f"sensor.{unique_id}_1_control_mode",
        ENTITY_AUTO_MODE: f"switch.{unique_id}_1_auto_mode",
        ENTITY_MANU_MODE: f"number.{unique_id}_1_manu_mode",
        ENTITY_BOOST_MODE: f"switch.{unique_id}_1_boost_mode",
        ENTITY_COMFORT_MODE: f"switch.{unique_id}_1_comfort_mode",
        ENTITY_LOWERING_MODE: f"switch.{unique_id}_1_lowering_mode",
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, device_entities)
    data.HA_DEVICES[address].entities.add(entity_id)

DEVICES = {
    'HM-CC-TC': make_simple_thermostat,
    'HM-CC-RT-DN': make_thermostat,
    'HM-CC-RT-DN-BoM': make_thermostat,
    'HM-TC-IT-WM-W-EU': make_wall_thermostat,
    'HM-CC-VG-1': make_group_thermostat,
}
