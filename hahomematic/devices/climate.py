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

class HMThermostat(climate):
    """
    Basic HomeMatic thermostat like HM-CC-RT-DN.
    This implementation reuses the existing entities associated
    to this device.
    """
    def __init__(self, interface_id, address, entity_id, unique_id):
        self.interface_id = interface_id
        self.address = address
        self.address_entity = self.address.lower()
        self.unique_id = unique_id
        LOG.debug("HMThermostat.__init__(%s, %s)", self.interface_id, self.address)
        self.client = data.CLIENTS[self.interface_id]
        self.proxy = self.client.proxy
        self.entity_id = entity_id
        self.name = data.NAMES.get(
            self.interface_id, {}).get(self.address, self.entity_id)
        self.ha_device = data.HA_DEVICES[self.address]
        self.channels = list(data.DEVICES[self.interface_id][self.address].keys())
        # self.channel_dict = dict(enumerate(self.channels))
        # Fetch MASTER paramset in case we need it.
        # if not PARAMSET_MASTER in data.PARAMSETS[self.interface_id][self.address]:
        #     self.client.fetch_paramset(self.address, PARAMSET_MASTER)
        self.paramsets = {
            self.address: data.PARAMSETS[self.interface_id][self.address]
        }
        for channel in self.channels:
            self.paramsets[channel] = data.PARAMSETS[self.interface_id][channel]
        # Subscribe for all events of this device
        if not self.address in data.EVENT_SUBSCRIPTIONS_DEVICE:
            data.EVENT_SUBSCRIPTIONS_DEVICE[self.address] = []
        data.EVENT_SUBSCRIPTIONS_DEVICE[self.address].append(self.event)
        self.update_callback = None
        if callable(config.CALLBACK_ENTITY_UPDATE):
            self.update_callback = config.CALLBACK_ENTITY_UPDATE
        self._entity_actual_temperature = f"number.{self.unique_id}_4_actual_temperature"
        self._entity_set_temperature = f"number.{self.unique_id}_4_set_temperature"
        self._entity_control_mode = f"sensor.{self.unique_id}_4_control_mode"
        self._entity_boost_state = f"sensor.{self.unique_id}_4_boost_state"
        self._entity_humidity = None
        self._entity_auto_mode = f"switch.{self.unique_id}_4_auto_mode"
        self._entity_manu_mode = f"switch.{self.unique_id}_4_manu_mode"
        self._entity_boost_mode = f"switch.{self.unique_id}_4_boost_mode"
        self._entity_comfort_mode = f"switch.{self.unique_id}_4_comfort_mode"
        self._entity_lowering_mode = f"switch.{self.unique_id}_4_lowering_mode"

    def event(self, interface_id, address, value_key, value):
        """
        Handle event for this device.
        """
        if interface_id == self.interface_id:
            LOG.debug("HMThermostat.event(%s, %s, %s, %s)",
                      interface_id, address, value_key, value)
            self.update_entity()

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self.update_callback is None:
            LOG.debug("Entity.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self.update_callback(self.entity_id)

    @property
    def _hm_control_mode(self):
        """
        Return current control mode.
        Will be one of: ['AUTO-MODE', 'MANU-MODE', 'PARTY-MODE', 'BOOST-MODE']
        (for HM-CC-RT-DN)
        """
        return data.ENTITIES[self._entity_control_mode].STATE

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

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
        if self._hm_control_mode == 'MANU-MODE':
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
        if control_mode == 'BOOST-MODE':
            return PRESET_BOOST
        # elif control_mode == 'PARTY-MODE':
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

def make_hmthermostat(interface_id, address):
    """
    Helper to create HMThermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    unique_id = generate_unique_id(address)
    entity_id = "climate.{}".format(unique_id)
    if entity_id in data.ENTITIES:
        LOG.debug("make_hmthermostat: Skipping %s (already exists)", entity_id)
    data.ENTITIES[entity_id] = HMThermostat(interface_id, address, entity_id, unique_id)
    data.HA_DEVICES[address].entities.add(entity_id)

DEVICES = {
    'HM-CC-RT-DN': make_hmthermostat,
    'HM-CC-RT-DN-BoM': make_hmthermostat,
}
