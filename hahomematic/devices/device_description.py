"""
This module contains device descriptions for custom entities.
"""
DD_CHANNELS = "channels"
DD_DEVICE = "device"
DD_DEFAULT_ENTITIES = "default_entities"
DD_ENTITIES = "entities"
DD_FIELDS = "fields"
DD_ADDRESS_PREFIX = "address_prefix"
DD_PARAM_NAME = "param_name"


FIELD_HUMIDITY = "humidity"
FIELD_TEMPERATURE = "temperature"
FIELD_SETPOINT = "setpoint"
FIELD_SET_POINT_MODE = "set_point_mode"
FIELD_CONTROL_MODE = "control_mode"
FIELD_BOOST_MODE = "boost_mode"
FIELD_PARTY_MODE = "party_mode"
FIELD_AUTO_MODE = "auto_mode"
FIELD_MANU_MODE = "manu_mode"
FIELD_COMFORT_MODE = "comfort_mode"
FIELD_LOWERING_MODE = "lowering_mode"


FIELD_DUTY_CYCLE = "duty_cycle"
FIELD_LOW_BAT = "low_bat"
FIELD_OPERATING_VOLTAGE = "operating_voltage"
FIELD_RSSI_DEVICE = "rssi_device"
FIELD_RSSI_PEER = "rssi_peer"
FIELD_SABOTAGE = "sabotage"


FIELD_STATE = "state"
FIELD_SWITCH_MAIN = "switch_main"
FIELD_SWITCH_V1 = "vswitch_1"
FIELD_SWITCH_V2 = "vswitch_2"
FIELD_COLOR = "color"
FIELD_LEVEL = "level"
FIELD_STATE = "state"
FIELD_ENERGY_COUNTER = "energie_counter"
FIELD_VOLTAGE = "voltage"
FIELD_FREQUENCY = "frequency"
FIELD_POWER = "power"
FIELD_CURRENT = "current"


device_description = {
    DD_DEFAULT_ENTITIES: {
        FIELD_DUTY_CYCLE: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "DUTY_CYCLE"},
        FIELD_LOW_BAT: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "LOW_BAT"},
        FIELD_LOW_BAT: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "LOWBAT"},
        FIELD_OPERATING_VOLTAGE: {
            DD_ADDRESS_PREFIX: 0,
            DD_PARAM_NAME: "OPERATING_VOLTAGE",
        },
        FIELD_RSSI_DEVICE: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "RSSI_DEVICE"},
        FIELD_RSSI_PEER: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "RSSI_PEER"},
        FIELD_SABOTAGE: {DD_ADDRESS_PREFIX: 0, DD_PARAM_NAME: "SABOTAGE"},
    },
    "SimpleThermostat": {
        DD_DEVICE: {
            DD_CHANNELS: [1],
            DD_FIELDS: {
                1: {
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_SETPOINT: "SET_TEMPERATURE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {},
    },
    "Thermostat": {
        DD_DEVICE: {
            DD_CHANNELS: [2],
            DD_FIELDS: {
                2: {
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_SETPOINT: "SET_TEMPERATURE",
                    FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_MANU_MODE: "MANU_MODE",
                    FIELD_COMFORT_MODE: "COMFORT_MODE",
                    FIELD_LOWERING_MODE: "LOWERING_MODE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {},
    },
    "IPThermostat": {
        DD_DEVICE: {
            DD_CHANNELS: [1],
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
            "attr": {},
        },
        DD_ENTITIES: {
            FIELD_HUMIDITY: {DD_ADDRESS_PREFIX: 1, DD_PARAM_NAME: "HUMIDITY"},
        },
    },
    "IPDimmer": {
        DD_DEVICE: {
            DD_CHANNELS: [4, 5, 6],
            DD_FIELDS: {
                4: {
                    FIELD_LEVEL: "LEVEL",
                },
                5: {
                    FIELD_LEVEL: "LEVEL",
                },
                6: {
                    FIELD_LEVEL: "LEVEL",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {},
    },
    "IPLight": {
        DD_DEVICE: {
            DD_CHANNELS: [4, 5, 6],
            DD_FIELDS: {
                4: {
                    FIELD_STATE: "STATE",
                },
                5: {
                    FIELD_STATE: "STATE",
                },
                6: {
                    FIELD_STATE: "STATE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {
            FIELD_STATE: {DD_ADDRESS_PREFIX: 3, DD_PARAM_NAME: "STATE"},
            FIELD_TEMPERATURE : {DD_ADDRESS_PREFIX: 7, DD_PARAM_NAME: "ACTUAL_TEMPERATURE"},
            FIELD_VOLTAGE: {DD_ADDRESS_PREFIX: 7, DD_PARAM_NAME: "VOLTAGE"},
            FIELD_ENERGY_COUNTER: {
                DD_ADDRESS_PREFIX: 7,
                DD_PARAM_NAME: "ENERGY_COUNTER",
            },
            FIELD_FREQUENCY: {DD_ADDRESS_PREFIX: 7, DD_PARAM_NAME: "FREQUENCY"},
            FIELD_POWER: {DD_ADDRESS_PREFIX: 7, DD_PARAM_NAME: "POWER"},
            FIELD_CURRENT: {DD_ADDRESS_PREFIX: 7, DD_PARAM_NAME: "CURRENT"},
        },
    },
    "IPLightBSL": {
        DD_DEVICE: {
            DD_CHANNELS: [8, 9, 10, 12, 13, 14],
            DD_FIELDS: {
                # 7: { Sensor
                #    FIELD_COLOR: "COLOR",
                #    FIELD_LEVEL: "LEVEL",
                # },
                8: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                9: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                10: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                # 11: { Sensor
                #    FIELD_COLOR: "COLOR",
                #    FIELD_LEVEL: "LEVEL",
                # },
                12: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                13: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                14: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {
            FIELD_STATE: {DD_ADDRESS_PREFIX: 3, DD_PARAM_NAME: "STATE"},
            FIELD_SWITCH_MAIN: {DD_ADDRESS_PREFIX: 4, DD_PARAM_NAME: "STATE"},
            FIELD_SWITCH_V1: {DD_ADDRESS_PREFIX: 5, DD_PARAM_NAME: "STATE"},
            FIELD_SWITCH_V2: {DD_ADDRESS_PREFIX: 6, DD_PARAM_NAME: "STATE"},
        },
    },
}
