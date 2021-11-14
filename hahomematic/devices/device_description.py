"""
This module contains device descriptions for custom entities.
"""
import logging
from enum import Enum

from voluptuous import Invalid, Optional, Required, Schema

DD_DEFAULT_ENTITIES = "default_entities"
DD_DEVICE_GROUPS = "device_groups"
DD_DEVICES = "devices"
DD_ENTITIES = "entities"
DD_FIELDS = "fields"
DD_FIELDS_REP = "fields_rep"
DD_PHY_CHANNEL = "phy_channel"
DD_VIRT_CHANNEL = "virt_channel"

FIELD_AUTO_MODE = "auto_mode"
FIELD_BOOST_MODE = "boost_mode"
FIELD_CHANNEL_COLOR = "channel_color"
FIELD_CHANNEL_LEVEL = "channel_level"
FIELD_CHANNEL_LEVEL_2 = "channel_level_2"
FIELD_CHANNEL_STATE = "channel_state"
FIELD_COLOR = "color"
FIELD_COMFORT_MODE = "comfort_mode"
FIELD_CONTROL_MODE = "control_mode"
FIELD_CURRENT = "current"
FIELD_DUTY_CYCLE = "duty_cycle"
FIELD_DUTYCYCLE = "dutycycle"
FIELD_ENERGY_COUNTER = "energy_counter"
FIELD_FREQUENCY = "frequency"
FIELD_HUMIDITY = "humidity"
FIELD_LEVEL = "level"
FIELD_LEVEL_2 = "level_2"
FIELD_LOW_BAT = "low_bat"
FIELD_LOWBAT = "lowbat"
FIELD_LOWERING_MODE = "lowering_mode"
FIELD_MANU_MODE = "manu_mode"
FIELD_OPERATING_VOLTAGE = "operating_voltage"
FIELD_PARTY_MODE = "party_mode"
FIELD_POWER = "power"
FIELD_RSSI_DEVICE = "rssi_device"
FIELD_RSSI_PEER = "rssi_peer"
FIELD_SABOTAGE = "sabotage"
FIELD_SET_POINT_MODE = "set_point_mode"
FIELD_SETPOINT = "setpoint"
FIELD_STATE = "state"
FIELD_STOP = "stop"
FIELD_SWITCH_MAIN = "switch_main"
FIELD_SWITCH_V1 = "vswitch_1"
FIELD_SWITCH_V2 = "vswitch_2"
FIELD_TEMPERATURE = "temperature"
FIELD_VOLTAGE = "voltage"

_LOGGER = logging.getLogger(__name__)


class Devices(Enum):
    RF_DIMMER = "RfDimmer"
    IP_LIGHT_BSL = "IPLightBSL"
    IP_DIMMER = "IPDimmer"
    IP_MULTI_DIMMER = "IPMultiDimmer"
    IP_WIRED_MULTI_DIMMER = "IPWiredMultiDimmer"
    IP_LIGHT = "IPLight"
    IP_THERMOSTAT = "IPThermostat"
    SIMPLE_RF_THERMOSTAT = "SimpleRfThermostat"
    RF_THERMOSTAT = "RfThermostat"
    IP_COVER = "IPCover"
    RF_COVER = "RfCover"


SCHEMA_DD_FIELD_DETAILS = Schema({Optional(str): str, Optional(str): str})

SCHEMA_DD_FIELD = Schema({Optional(int): SCHEMA_DD_FIELD_DETAILS})

SCHEMA_DD_DEVICE_GROUP = Schema(
    {
        Required(DD_PHY_CHANNEL): [int],
        Required(DD_VIRT_CHANNEL): [int],
        Required(DD_FIELDS_REP, default={}): SCHEMA_DD_FIELD_DETAILS,
        Required(DD_FIELDS): SCHEMA_DD_FIELD,
    }
)

SCHEMA_DD_DEVICE_GROUPS = Schema(
    {
        Required(DD_DEVICE_GROUPS): [SCHEMA_DD_DEVICE_GROUP],
        Required(DD_ENTITIES): SCHEMA_DD_FIELD,
    }
)

SCHEMA_DEVICE_DESCRIPTION = Schema(
    {
        Required(DD_DEFAULT_ENTITIES): SCHEMA_DD_FIELD,
        Required(DD_DEVICES): Schema(
            {
                Required(Devices): SCHEMA_DD_DEVICE_GROUPS,
            }
        ),
    }
)


device_description = {
    DD_DEFAULT_ENTITIES: {
        0: {
            FIELD_DUTY_CYCLE: "DUTY_CYCLE",
            FIELD_DUTYCYCLE: "DUTYCYCLE",
            FIELD_LOW_BAT: "LOW_BAT",
            FIELD_LOWBAT: "LOWBAT",
            FIELD_OPERATING_VOLTAGE: "OPERATING_VOLTAGE",
            FIELD_RSSI_DEVICE: "RSSI_DEVICE",
            FIELD_RSSI_PEER: "RSSI_PEER",
            FIELD_SABOTAGE: "SABOTAGE",
        }
    },
    DD_DEVICES: {
        Devices.SIMPLE_RF_THERMOSTAT: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [],
                    DD_VIRT_CHANNEL: [],
                    DD_FIELDS_REP: {},
                    DD_FIELDS: {
                        1: {
                            FIELD_HUMIDITY: "HUMIDITY",
                            FIELD_TEMPERATURE: "TEMPERATURE",
                        },
                        2: {
                            FIELD_SETPOINT: "SETPOINT",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.RF_THERMOSTAT: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [],
                    DD_VIRT_CHANNEL: [],
                    DD_FIELDS_REP: {},
                    DD_FIELDS: {
                        1: {
                            FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                            FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                            FIELD_SETPOINT: "SET_TEMPERATURE",
                            FIELD_CONTROL_MODE: "CONTROL_MODE",
                            FIELD_BOOST_MODE: "BOOST_MODE",
                            FIELD_AUTO_MODE: "AUTO_MODE",
                            FIELD_MANU_MODE: "MANU_MODE",
                            FIELD_COMFORT_MODE: "COMFORT_MODE",
                            FIELD_LOWERING_MODE: "LOWERING_MODE",
                        },
                        2: {
                            FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                            FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                            FIELD_SETPOINT: "SET_TEMPERATURE",
                            FIELD_CONTROL_MODE: "CONTROL_MODE",
                            FIELD_BOOST_MODE: "BOOST_MODE",
                            FIELD_AUTO_MODE: "AUTO_MODE",
                            FIELD_MANU_MODE: "MANU_MODE",
                            FIELD_COMFORT_MODE: "COMFORT_MODE",
                            FIELD_LOWERING_MODE: "LOWERING_MODE",
                        },
                        4: {
                            FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                            FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                            FIELD_SETPOINT: "SET_TEMPERATURE",
                            FIELD_CONTROL_MODE: "CONTROL_MODE",
                            FIELD_BOOST_MODE: "BOOST_MODE",
                            FIELD_AUTO_MODE: "AUTO_MODE",
                            FIELD_MANU_MODE: "MANU_MODE",
                            FIELD_COMFORT_MODE: "COMFORT_MODE",
                            FIELD_LOWERING_MODE: "LOWERING_MODE",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.IP_THERMOSTAT: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [],
                    DD_VIRT_CHANNEL: [],
                    DD_FIELDS_REP: {},
                    DD_FIELDS: {
                        1: {
                            FIELD_HUMIDITY: "HUMIDITY",
                            FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                            FIELD_SETPOINT: "SET_POINT_TEMPERATURE",
                            FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                            FIELD_CONTROL_MODE: "CONTROL_MODE",
                            FIELD_BOOST_MODE: "BOOST_MODE",
                            FIELD_PARTY_MODE: "PARTY_MODE",
                            FIELD_AUTO_MODE: "AUTO_MODE",
                        },
                    },
                },
            ],
            DD_ENTITIES: {
                1: {
                    FIELD_HUMIDITY: "HUMIDITY",
                }
            },
        },
        Devices.IP_DIMMER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [4],
                    DD_VIRT_CHANNEL: [5, 6],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        3: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.IP_MULTI_DIMMER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [5],
                    DD_VIRT_CHANNEL: [6, 7],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        4: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
                {
                    DD_PHY_CHANNEL: [9],
                    DD_VIRT_CHANNEL: [10, 11],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        8: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
                {
                    DD_PHY_CHANNEL: [13],
                    DD_VIRT_CHANNEL: [14, 15],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        12: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.IP_WIRED_MULTI_DIMMER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [2],
                    DD_VIRT_CHANNEL: [3, 4],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        1: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
                {
                    DD_PHY_CHANNEL: [6],
                    DD_VIRT_CHANNEL: [7, 8],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        5: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
                {
                    DD_PHY_CHANNEL: [10],
                    DD_VIRT_CHANNEL: [11, 12],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        9: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.RF_DIMMER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [1, 2, 3, 4],
                    DD_VIRT_CHANNEL: [],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {},
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.IP_LIGHT: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [4],
                    DD_VIRT_CHANNEL: [5, 6],
                    DD_FIELDS_REP: {
                        FIELD_STATE: "STATE",
                    },
                    DD_FIELDS: {
                        3: {
                            FIELD_CHANNEL_STATE: "STATE",
                        },
                    },
                },
            ],
            DD_ENTITIES: {
                7: {
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_VOLTAGE: "VOLTAGE",
                    FIELD_ENERGY_COUNTER: "ENERGY_COUNTER",
                    FIELD_FREQUENCY: "FREQUENCY",
                    FIELD_POWER: "POWER",
                    FIELD_CURRENT: "CURRENT",
                },
            },
        },
        Devices.IP_LIGHT_BSL: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [8],
                    DD_VIRT_CHANNEL: [9, 10],
                    DD_FIELDS_REP: {
                        FIELD_COLOR: "COLOR",
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        7: {
                            FIELD_CHANNEL_COLOR: "COLOR",
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
                {
                    DD_PHY_CHANNEL: [12],
                    DD_VIRT_CHANNEL: [13, 14],
                    DD_FIELDS_REP: {
                        FIELD_COLOR: "COLOR",
                        FIELD_LEVEL: "LEVEL",
                    },
                    DD_FIELDS: {
                        11: {
                            FIELD_CHANNEL_COLOR: "COLOR",
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                        },
                    },
                },
            ],
            DD_ENTITIES: {
                3: {
                    FIELD_STATE: "STATE",
                },
                4: {
                    FIELD_SWITCH_MAIN: "STATE",
                },
                5: {
                    FIELD_SWITCH_V1: "STATE",
                },
                6: {
                    FIELD_SWITCH_V2: "STATE",
                },
            },
        },
        Devices.IP_COVER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [4],
                    DD_VIRT_CHANNEL: [5, 6],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                        FIELD_LEVEL_2: "LEVEL_2",
                        FIELD_STOP: "STOP",
                    },
                    DD_FIELDS: {
                        3: {
                            FIELD_CHANNEL_LEVEL: "LEVEL",
                            FIELD_CHANNEL_LEVEL_2: "LEVEL_2",
                        },
                    },
                },
            ],
            DD_ENTITIES: {},
        },
        Devices.RF_COVER: {
            DD_DEVICE_GROUPS: [
                {
                    DD_PHY_CHANNEL: [1, 2, 3, 4],
                    DD_VIRT_CHANNEL: [],
                    DD_FIELDS_REP: {
                        FIELD_LEVEL: "LEVEL",
                        FIELD_LEVEL_2: "LEVEL_2",
                        FIELD_STOP: "STOP",
                    },
                    DD_FIELDS: {},
                },
            ],
            DD_ENTITIES: {},
        },
    },
}


def validate_device_description():
    try:
        return SCHEMA_DEVICE_DESCRIPTION(device_description)
    except Invalid as err:
        _LOGGER.error(
            "The DEVICE_DESCRIPTION could not be validated. %s, %s", err.path, err.msg
        )
        return None


def get_default_entities():
    """Return the default entities."""
    return device_description[DD_DEFAULT_ENTITIES]


def get_device_groups(device_enum: Devices):
    """Return the device group."""
    device_desc = device_description[DD_DEVICES].get(device_enum)
    if device_desc:
        return device_desc[DD_DEVICE_GROUPS]
    return None


def get_device_entities(device_enum: Devices):
    """Return the device entities."""
    device_desc = device_description[DD_DEVICES].get(device_enum)
    if device_desc:
        return device_desc[DD_ENTITIES]
    return None
