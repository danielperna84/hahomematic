# pylint: disable=line-too-long
"""
Code to create the required entities for thermostat devices.
"""

import logging

from hahomematic import data, config
from hahomematic.platforms.climate import climate
from hahomematic.helpers import generate_unique_id
from hahomematic.const import (
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    PARAMSET_VALUES,
)

LOG = logging.getLogger(__name__)

NODE_ACTUAL_TEMPERATURE = 'ENTITY_ACTUAL_TEMPERATURE'
NODE_SET_TEMPERATURE = 'ENTITY_SET_TEMPERATURE'
NODE_CONTROL_MODE = 'ENTITY_CONTROL_MODE'
NODE_HUMIDITY = 'ENTITY_HUMIDITY'
NODE_AUTO_MODE = 'ENTITY_AUTO_MODE'
NODE_MANU_MODE = 'ENTITY_MANU_MODE'
NODE_BOOST_MODE = 'ENTITY_BOOST_MODE'
NODE_AWAY_MODE = 'ENTITY_AWAY_MODE'
NODE_PARTY_MODE = 'ENTITY_PARTY_MODE'
NODE_SET_POINT_MODE = 'ENTITY_SET_POINT_MODE'
NODE_COMFORT_MODE = 'ENTITY_COMFORT_MODE'
NODE_LOWERING_MODE = 'ENTITY_LOWERING_MODE'

PARAM_TEMPERATURE = 'TEMPERATURE'
PARAM_HUMIDITY = 'HUMIDITY'
PARAM_SETPOINT = 'SETPOINT'

HM_MODE_AUTO = 0
HM_MODE_MANU = 1
HM_MODE_AWAY = 2
HM_MODE_BOOST = 3
HMIP_SET_POINT_MODE_AUTO = 0
HMIP_SET_POINT_MODE_MANU = 1
HMIP_SET_POINT_MODE_AWAY = 2

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

# pylint: disable=too-many-instance-attributes
class SimpleThermostat(climate):
    """Simple classic HomeMatic thermostat HM-CC-TC."""
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, address, entity_id, unique_id):
        LOG.debug("SimpleThermostat.__init__(%s, %s, %s, %s)",
                  interface_id, address, entity_id, unique_id)
        self.interface_id = interface_id
        self.address = address
        self.client = data.CLIENTS[self.interface_id]
        self.proxy = self.client.proxy
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
        # Parameter defaults
        self.humidity = None # Channel 1
        self.temperature = None # Channel 1
        self.setpoint = None # Channel 2

    def event(self, interface_id, address, value_key, value):
        """
        Handle events for this device.
        """
        if interface_id != self.interface_id:
            return
        if address not in [f"{self.address}:1", f"{self.address}:2"]:
            return
        LOG.debug("SimpleThermostat.event(%s, %s, %s, %s)",
                  interface_id, address, value_key, value)
        if value_key == PARAM_TEMPERATURE:
            self.temperature = value
        elif value_key == PARAM_HUMIDITY:
            self.humidity = value
        elif value_key == PARAM_SETPOINT:
            self.setpoint = value
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
        return data.PARAMSETS[self.interface_id][
            f"{self.address}:1"][PARAMSET_VALUES][PARAM_TEMPERATURE][ATTR_HM_MIN]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return data.PARAMSETS[self.interface_id][
            f"{self.address}:1"][PARAMSET_VALUES][PARAM_TEMPERATURE][ATTR_HM_MAX]

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
        if self.humidity is None:
            return self.proxy.getValue(f"{self.address}:1", PARAM_HUMIDITY)
        return self.humidity

    @property
    def current_temperature(self):
        """Return current temperature."""
        if self.temperature is None:
            return self.proxy.getValue(f"{self.address}:1", PARAM_TEMPERATURE)
        return self.temperature

    @property
    def target_temperature(self):
        """Return target temperature."""
        if self.setpoint is None:
            return self.proxy.getValue(f"{self.address}:2", PARAM_SETPOINT)
        return self.setpoint

    # pylint: disable=inconsistent-return-statements
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        return self.proxy.getValue(f"{self.address}:2", PARAM_SETPOINT, float(temperature))

class Thermostat(climate):
    """Classic HomeMatic thermostat like HM-CC-RT-DN."""
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, address, entity_id, unique_id, nodes):
        LOG.debug("Thermostat.__init__(%s, %s, %s, %s)",
                  interface_id, address, entity_id, unique_id)
        self.interface_id = interface_id
        self.address = address
        self.client = data.CLIENTS[self.interface_id]
        self.proxy = self.client.proxy
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
        self._node_actual_temperature = nodes.get(NODE_ACTUAL_TEMPERATURE)
        self._node_set_temperature = nodes.get(NODE_SET_TEMPERATURE)
        self._node_control_mode = nodes.get(NODE_CONTROL_MODE)
        self._node_humidity = nodes.get(NODE_HUMIDITY)
        self._node_auto_mode = nodes.get(NODE_AUTO_MODE)
        self._node_manu_mode = nodes.get(NODE_MANU_MODE)
        self._node_boost_mode = nodes.get(NODE_BOOST_MODE)
        self._node_comfort_mode = nodes.get(NODE_COMFORT_MODE)
        self._node_lowering_mode = nodes.get(NODE_LOWERING_MODE)
        # Parameter defaults
        self.humidity = None
        self.temperature = None
        self.setpoint = None
        self.control_mode = None

    def event(self, interface_id, address, value_key, value):
        """
        Handle event for this device.
        """
        if interface_id != self.interface_id:
            return
        if address != self._node_actual_temperature[0]:
            return
        LOG.debug("Thermostat.event(%s, %s, %s, %s)",
                  interface_id, address, value_key, value)
        if value_key == self._node_actual_temperature[1]:
            self.temperature = value
        elif value_key == self._node_set_temperature[1]:
            self.setpoint = value
        elif value_key == self._node_control_mode[1]:
            self.control_mode = value
        elif self._node_humidity is not None and value_key == self._node_humidity[1]:
            self.humidity = value
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
        return data.PARAMSETS[self.interface_id][
            self._node_actual_temperature[0]][
                PARAMSET_VALUES][self._node_actual_temperature[1]][ATTR_HM_MIN]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return data.PARAMSETS[self.interface_id][
            self._node_actual_temperature[0]][
                PARAMSET_VALUES][self._node_actual_temperature[1]][ATTR_HM_MAX]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        if self.temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self.control_mode == HM_MODE_MANU:
            return HVAC_MODE_HEAT
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self.control_mode is None:
            return PRESET_NONE
        if self.control_mode == HM_MODE_BOOST:
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
        if self.humidity is None and self._node_humidity is not None:
            self.humidity = self.proxy.getValue(self._node_humidity[0],
                                                self._node_humidity[1])
        return self.humidity

    @property
    def current_temperature(self):
        """Return current temperature."""
        if self.temperature is None:
            self.temperature = self.proxy.getValue(self._node_actual_temperature[0],
                                                   self._node_actual_temperature[1])
        return self.temperature

    @property
    def target_temperature(self):
        """Return target temperature."""
        if self.setpoint is None:
            self.setpoint = self.proxy.getValue(self._node_set_temperature[0],
                                                self._node_set_temperature[1])
        return self.setpoint

    # pylint: disable=inconsistent-return-statements
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        self.proxy.setValue(self._node_set_temperature[0],
                            self._node_set_temperature[1],
                            float(temperature))

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self.proxy.setValue(self._node_auto_mode[0],
                                self._node_auto_mode[1],
                                True)
        elif hvac_mode == HVAC_MODE_HEAT:
            self.proxy.setValue(self._node_manu_mode[0],
                                self._node_manu_mode[1],
                                self.max_temp)
        elif hvac_mode == HVAC_MODE_OFF:
            self.set_temperature(temperature=self.min_temp)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            self.proxy.setValue(self._node_boost_mode[0],
                                self._node_boost_mode[1],
                                True)
        elif preset_mode == PRESET_COMFORT:
            self.proxy.setValue(self._node_comfort_mode[0],
                                self._node_comfort_mode[1],
                                True)
        elif preset_mode == PRESET_ECO:
            self.proxy.setValue(self._node_lowering_mode[0],
                                self._node_lowering_mode[1],
                                True)

class IPThermostat(climate):
    """homematic IP thermostat like HmIP-eTRV-B."""
    # pylint: disable=too-many-arguments
    def __init__(self, interface_id, address, entity_id, unique_id, nodes):
        LOG.debug("IPThermostat.__init__(%s, %s, %s, %s)",
                  interface_id, address, entity_id, unique_id)
        self.interface_id = interface_id
        self.address = address
        self.client = data.CLIENTS[self.interface_id]
        self.proxy = self.client.proxy
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
        self._node_actual_temperature = nodes.get(NODE_ACTUAL_TEMPERATURE)
        self._node_set_temperature = nodes.get(NODE_SET_TEMPERATURE)
        self._node_control_mode = nodes.get(NODE_CONTROL_MODE)
        self._node_humidity = nodes.get(NODE_HUMIDITY)
        self._node_set_point_mode = nodes.get(NODE_SET_POINT_MODE)
        self._node_boost_mode = nodes.get(NODE_BOOST_MODE)
        self._node_party_mode = nodes.get(NODE_PARTY_MODE)
        # Parameter defaults
        self.humidity = None
        self.temperature = None
        self.setpoint = None
        self.set_point_mode = None
        self.control_mode = None
        self.boost_mode = None
        self.party_mode = None

    def event(self, interface_id, address, value_key, value):
        """
        Handle event for this device.
        """
        if interface_id != self.interface_id:
            return
        if address != self._node_actual_temperature[0]:
            return
        LOG.debug("IPThermostat.event(%s, %s, %s, %s)",
                  interface_id, address, value_key, value)
        if value_key == self._node_actual_temperature[1]:
            self.temperature = value
        elif value_key == self._node_set_temperature[1]:
            self.setpoint = value
        elif value_key == self._node_set_point_mode[1]:
            self.set_point_mode = value
        elif value_key == self._node_boost_mode[1]:
            self.boost_mode = value
        elif value_key == self._node_party_mode[1]:
            self.party_mode = value
        elif self._node_humidity is not None and value_key == self._node_humidity[1]:
            self.humidity = value
        self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("IPThermostat.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.entity_id)

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
        return data.PARAMSETS[self.interface_id][
            self._node_actual_temperature[0]][
                PARAMSET_VALUES][self._node_actual_temperature[1]][ATTR_HM_MIN]

    @property
    def max_temp(self):
        """Return the maximum temperature."""
        return data.PARAMSETS[self.interface_id][
            self._node_actual_temperature[0]][
                PARAMSET_VALUES][self._node_actual_temperature[1]][ATTR_HM_MAX]

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.5

    @property
    def hvac_mode(self):
        """Return hvac operation mode."""
        if self.temperature <= self.min_temp:
            return HVAC_MODE_OFF
        if self.set_point_mode == HMIP_SET_POINT_MODE_MANU:
            return HVAC_MODE_HEAT
        if self.set_point_mode == HMIP_SET_POINT_MODE_AUTO:
            return HVAC_MODE_AUTO
        return HVAC_MODE_AUTO

    @property
    def hvac_modes(self):
        """Return the list of available hvac operation modes."""
        return [HVAC_MODE_AUTO, HVAC_MODE_HEAT, HVAC_MODE_OFF]

    @property
    def preset_mode(self):
        """Return the current preset mode."""
        if self.boost_mode:
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
    def current_humidity(self):
        """Return the current humidity."""
        if self.humidity is None and self._node_humidity is not None:
            self.humidity = self.proxy.getValue(self._node_humidity[0],
                                                self._node_humidity[1])
        return self.humidity

    @property
    def current_temperature(self):
        """Return current temperature."""
        if self.temperature is None:
            self.temperature = self.proxy.getValue(self._node_actual_temperature[0],
                                                   self._node_actual_temperature[1])
        return self.temperature

    @property
    def target_temperature(self):
        """Return target temperature."""
        if self.setpoint is None:
            self.setpoint = self.proxy.getValue(self._node_set_temperature[0],
                                                self._node_set_temperature[1])
        return self.setpoint

    # pylint: disable=inconsistent-return-statements
    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return None
        self.proxy.setValue(self._node_set_temperature[0],
                            self._node_set_temperature[1],
                            float(temperature))

    def set_hvac_mode(self, hvac_mode):
        """Set new target hvac mode."""
        if hvac_mode == HVAC_MODE_AUTO:
            self.proxy.setValue(self._node_control_mode[0],
                                self._node_control_mode[1],
                                HMIP_SET_POINT_MODE_AUTO)
        elif hvac_mode == HVAC_MODE_HEAT:
            self.proxy.setValue(self._node_control_mode[0],
                                self._node_control_mode[1],
                                HMIP_SET_POINT_MODE_MANU)
            self.set_temperature(temperature=self.max_temp)
        elif hvac_mode == HVAC_MODE_OFF:
            self.proxy.setValue(self._node_control_mode[0],
                                self._node_control_mode[1],
                                HMIP_SET_POINT_MODE_MANU)
            self.set_temperature(temperature=self.min_temp)

    def set_preset_mode(self, preset_mode):
        """Set new preset mode."""
        if preset_mode == PRESET_BOOST:
            self.proxy.setValue(self._node_boost_mode[0],
                                self._node_boost_mode[1],
                                True)

def make_simple_thermostat(interface_id, address):
    """
    Helper to create SimpleThermostat entities.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_simple_thermostat: Skipping %s (already exists)", entity_id)
    data.ENTITIES[entity_id] = SimpleThermostat(interface_id, address, entity_id, unique_id)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:4', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:4', 'SET_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:4', 'CONTROL_MODE'),
        NODE_AUTO_MODE: (f'{address}:4', 'AUTO_MODE'),
        NODE_MANU_MODE: (f'{address}:4', 'MANU_MODE'),
        NODE_BOOST_MODE: (f'{address}:4', 'BOOST_MODE'),
        NODE_COMFORT_MODE: (f'{address}:4', 'COMFORT_MODE'),
        NODE_LOWERING_MODE: (f'{address}:4', 'LOWERING_MODE'),
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_max_thermostat(interface_id, address):
    """
    Helper to create MAX! Thermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:1', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:1', 'SET_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:1', 'CONTROL_MODE'),
        NODE_AUTO_MODE: (f'{address}:1', 'AUTO_MODE'),
        NODE_MANU_MODE: (f'{address}:1', 'MANU_MODE'),
        NODE_BOOST_MODE: (f'{address}:1', 'BOOST_MODE'),
        NODE_COMFORT_MODE: (f'{address}:1', 'COMFORT_MODE'),
        NODE_LOWERING_MODE: (f'{address}:1', 'LOWERING_MODE'),
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_wall_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities for wall-thermostats.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_wall_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:2', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:2', 'SET_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:2', 'CONTROL_MODE'),
        NODE_AUTO_MODE: (f'{address}:2', 'AUTO_MODE'),
        NODE_MANU_MODE: (f'{address}:2', 'MANU_MODE'),
        NODE_BOOST_MODE: (f'{address}:2', 'BOOST_MODE'),
        NODE_COMFORT_MODE: (f'{address}:2', 'COMFORT_MODE'),
        NODE_LOWERING_MODE: (f'{address}:2', 'LOWERING_MODE'),
        NODE_HUMIDITY: (f'{address}:2', 'HUMIDITY'),
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_group_thermostat(interface_id, address):
    """
    Helper to create Thermostat entities for heating groups.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_group_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:1', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:1', 'SET_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:1', 'CONTROL_MODE'),
        NODE_AUTO_MODE: (f'{address}:1', 'AUTO_MODE'),
        NODE_MANU_MODE: (f'{address}:1', 'MANU_MODE'),
        NODE_BOOST_MODE: (f'{address}:1', 'BOOST_MODE'),
        NODE_COMFORT_MODE: (f'{address}:1', 'COMFORT_MODE'),
        NODE_LOWERING_MODE: (f'{address}:1', 'LOWERING_MODE'),
    }
    data.ENTITIES[entity_id] = Thermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_ip_thermostat(interface_id, address):
    """
    Helper to create IPThermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_ip_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:1', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:1', 'SET_POINT_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:1', 'CONTROL_MODE'),
        NODE_SET_POINT_MODE: (f'{address}:1', 'SET_POINT_MODE'),
        NODE_BOOST_MODE: (f'{address}:1', 'BOOST_MODE'),
        NODE_PARTY_MODE: (f'{address}:1', 'PARTY_MODE'),
    }
    data.ENTITIES[entity_id] = IPThermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

def make_ip_wall_thermostat(interface_id, address):
    """
    Helper to create IPThermostat entities for wall-thermostats.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_ip_thermostat: Skipping %s (already exists)", entity_id)
    nodes = {
        NODE_ACTUAL_TEMPERATURE: (f'{address}:1', 'ACTUAL_TEMPERATURE'),
        NODE_SET_TEMPERATURE: (f'{address}:1', 'SET_POINT_TEMPERATURE'),
        NODE_CONTROL_MODE: (f'{address}:1', 'CONTROL_MODE'),
        NODE_SET_POINT_MODE: (f'{address}:1', 'SET_POINT_MODE'),
        NODE_BOOST_MODE: (f'{address}:1', 'BOOST_MODE'),
        NODE_PARTY_MODE: (f'{address}:1', 'PARTY_MODE'),
        NODE_HUMIDITY: (f'{address}:1', 'HUMIDITY'),
    }
    data.ENTITIES[entity_id] = IPThermostat(interface_id, address, entity_id, unique_id, nodes)
    data.HA_DEVICES[address].entities.add(entity_id)
    return [entity_id]

DEVICES = {
    'BC-RT-TRX-CyG': make_max_thermostat,
    'BC-RT-TRX-CyG-2': make_max_thermostat,
    'BC-RT-TRX-CyG-3': make_max_thermostat,
    'BC-RT-TRX-CyG-4': make_max_thermostat,
    'BC-RT-TRX-CyN': make_max_thermostat,
    'BC-TC-C-WM-2': make_max_thermostat,
    'BC-TC-C-WM-4': make_max_thermostat,
    'HM-CC-RT-DN': make_thermostat,
    'HM-CC-RT-DN-BoM': make_thermostat,
    'HM-CC-TC': make_simple_thermostat,
    'HM-CC-VG-1': make_group_thermostat,
    'HM-TC-IT-WM-W-EU': make_wall_thermostat,
    'HmIP-BWTH': make_ip_wall_thermostat,
    'HmIP-BWTH24': make_ip_wall_thermostat,
    'HMIP-eTRV': make_ip_thermostat,
    'HmIP-eTRV': make_ip_thermostat,
    'HmIP-eTRV-2': make_ip_thermostat,
    'HmIP-eTRV-2-UK': make_ip_thermostat,
    'HmIP-eTRV-B': make_ip_thermostat,
    'HmIP-eTRV-B-UK': make_ip_thermostat,
    'HmIP-eTRV-B1': make_ip_thermostat,
    'HmIP-eTRV-C': make_ip_thermostat,
    'HmIP-eTRV-C-2': make_ip_thermostat,
    'HmIP-HEATING': make_ip_thermostat,
    'HmIP-STH': make_ip_wall_thermostat,
    'HmIP-STHD': make_ip_wall_thermostat,
    'HMIP-WTH': make_ip_wall_thermostat,
    'HmIP-WTH': make_ip_wall_thermostat,
    'HMIP-WTH-2': make_ip_wall_thermostat,
    'HmIP-WTH-2': make_ip_wall_thermostat,
    'HMIP-WTH-B': make_ip_wall_thermostat,
    'HmIP-WTH-B': make_ip_wall_thermostat,
    'HmIPW-STH': make_ip_wall_thermostat,
    'HmIPW-WTH': make_ip_wall_thermostat,
    'Thermostat AA': make_ip_thermostat,
    'Thermostat AA GB': make_ip_thermostat,
    'ZEL STG RM FWT': make_simple_thermostat,
}
