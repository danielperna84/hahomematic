"""
This module contains device descriptions for custom entities.
"""
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

device_description = {
    DD_DEFAULT_ENTITIES: {
        FIELD_DUTY_CYCLE: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "DUTY_CYCLE"},
        FIELD_LOW_BAT: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "LOW_BAT"},
        FIELD_LOW_BAT: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "LOWBAT"},
        FIELD_OPERATING_VOLTAGE: {
            DD_ADDRESS_PREFIX: ":0",
            DD_PARAM_NAME: "OPERATING_VOLTAGE",
        },
        FIELD_RSSI_DEVICE: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "RSSI_DEVICE"},
        FIELD_RSSI_PEER: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "RSSI_PEER"},
        FIELD_SABOTAGE: {DD_ADDRESS_PREFIX: ":0", DD_PARAM_NAME: "SABOTAGE"},
    },
    "SimpleThermostat": {
        DD_DEVICE: {
            DD_FIELDS: {
                FIELD_HUMIDITY: {DD_ADDRESS_PREFIX: ":1", DD_PARAM_NAME: "HUMIDITY"},
                FIELD_TEMPERATURE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "ACTUAL_TEMPERATURE",
                },
                FIELD_SETPOINT: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "SET_TEMPERATURE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {},
    },
    "Thermostat": {
        DD_DEVICE: {
            DD_FIELDS: {
                FIELD_HUMIDITY: {DD_ADDRESS_PREFIX: ":2", DD_PARAM_NAME: "HUMIDITY"},
                FIELD_TEMPERATURE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "ACTUAL_TEMPERATURE",
                },
                FIELD_SETPOINT: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "SET_TEMPERATURE",
                },
                FIELD_SET_POINT_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "SET_POINT_MODE",
                },
                FIELD_CONTROL_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "CONTROL_MODE",
                },
                FIELD_BOOST_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "BOOST_MODE",
                },
                FIELD_AUTO_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "AUTO_MODE",
                },
                FIELD_MANU_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "MANU_MODE",
                },
                FIELD_COMFORT_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "COMFORT_MODE",
                },
                FIELD_LOWERING_MODE: {
                    DD_ADDRESS_PREFIX: ":2",
                    DD_PARAM_NAME: "LOWERING_MODE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {},
    },
    "IPThermostat": {
        DD_DEVICE: {
            DD_FIELDS: {
                FIELD_HUMIDITY: {DD_ADDRESS_PREFIX: ":1", DD_PARAM_NAME: "HUMIDITY"},
                FIELD_TEMPERATURE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "ACTUAL_TEMPERATURE",
                },
                FIELD_SETPOINT: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "SET_POINT_TEMPERATURE",
                },
                FIELD_SET_POINT_MODE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "SET_POINT_MODE",
                },
                FIELD_CONTROL_MODE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "CONTROL_MODE",
                },
                FIELD_BOOST_MODE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "BOOST_MODE",
                },
                FIELD_PARTY_MODE: {
                    DD_ADDRESS_PREFIX: ":1",
                    DD_PARAM_NAME: "PARTY_MODE",
                },
            },
            "attr": {},
        },
        DD_ENTITIES: {
            FIELD_HUMIDITY: {DD_ADDRESS_PREFIX: ":1", DD_PARAM_NAME: "HUMIDITY"},
        },
    },
}
