"""
This module contains device descriptions for custom entities.
"""
from copy import copy
from enum import Enum
import logging

from voluptuous import Invalid, Optional, Required, Schema

from hahomematic.helpers import generate_unique_id

DD_DEFAULT_ENTITIES = "default_entities"
DD_DEVICE_GROUP = "device_group"
DD_DEVICES = "devices"
DD_ADDITIONAL_ENTITIES = "additional_entities"
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
FIELD_LOCK_STATE = "lock_state"
FIELD_LOCK_TARGET_LEVEL = "lock_target_level"
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
    """Enum for device_descriptions."""

    IP_COVER = "IPCover"
    IP_DIMMER = "IPDimmer"
    IP_LIGHT_SWITCH = "IPLightSwitch"
    IP_LIGHT_BSL = "IPLightBSL"
    IP_LOCK = "IPLock"
    IP_THERMOSTAT = "IPThermostat"
    RF_COVER = "RfCover"
    RF_DIMMER = "RfDimmer"
    RF_THERMOSTAT = "RfThermostat"
    SIMPLE_RF_THERMOSTAT = "SimpleRfThermostat"


SCHEMA_DD_FIELD_DETAILS = Schema({Optional(str): str, Optional(str): str})

SCHEMA_DD_FIELD = Schema({Optional(int): SCHEMA_DD_FIELD_DETAILS})

SCHEMA_DD_DEVICE_GROUP = Schema(
    {
        Required(DD_PHY_CHANNEL): [int],
        Required(DD_VIRT_CHANNEL): [int],
        Required(DD_FIELDS_REP, default={}): SCHEMA_DD_FIELD_DETAILS,
        Optional(DD_FIELDS): SCHEMA_DD_FIELD,
    }
)

SCHEMA_DD_DEVICE_GROUPS = Schema(
    {
        Required(DD_DEVICE_GROUP): SCHEMA_DD_DEVICE_GROUP,
        Optional(DD_ADDITIONAL_ENTITIES): SCHEMA_DD_FIELD,
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
            FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
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
        Devices.IP_COVER: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
                DD_FIELDS: {
                    0: {
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                        FIELD_CHANNEL_LEVEL_2: "LEVEL_2",
                    },
                },
            },
        },
        Devices.IP_DIMMER: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1],
                DD_VIRT_CHANNEL: [2, 3],
                DD_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                },
                DD_FIELDS: {
                    0: {
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        Devices.IP_LIGHT_BSL: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1],
                DD_VIRT_CHANNEL: [2, 3],
                DD_FIELDS_REP: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                },
                DD_FIELDS: {
                    0: {
                        FIELD_CHANNEL_COLOR: "COLOR",
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        Devices.IP_LIGHT_SWITCH: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1],
                DD_VIRT_CHANNEL: [2, 3],
                DD_FIELDS_REP: {
                    FIELD_STATE: "STATE",
                },
                DD_FIELDS: {
                    0: {
                        FIELD_CHANNEL_STATE: "STATE",
                    },
                },
            },
            DD_ADDITIONAL_ENTITIES: {
                4: {
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_CURRENT: "CURRENT",
                    FIELD_ENERGY_COUNTER: "ENERGY_COUNTER",
                    FIELD_FREQUENCY: "FREQUENCY",
                    FIELD_POWER: "POWER",
                    FIELD_VOLTAGE: "VOLTAGE",
                },
            },
        },
        Devices.IP_LOCK: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {},
                DD_FIELDS: {
                    1: {
                        FIELD_LOCK_STATE: "LOCK_STATE",
                        FIELD_LOCK_TARGET_LEVEL: "LOCK_TARGET_LEVEL",
                    }
                },
            },
        },
        Devices.IP_THERMOSTAT: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {
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
            DD_ADDITIONAL_ENTITIES: {
                1: {
                    FIELD_HUMIDITY: "HUMIDITY",
                }
            },
        },
        Devices.RF_COVER: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1, 2, 3, 4],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
            },
        },
        Devices.RF_DIMMER: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1, 2, 3, 4],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                },
                DD_FIELDS: {},
            },
        },
        Devices.RF_THERMOSTAT: {
            DD_DEVICE_GROUP: {
                DD_PHY_CHANNEL: [1, 2, 3, 4],
                DD_VIRT_CHANNEL: [],
                DD_FIELDS_REP: {
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
        Devices.SIMPLE_RF_THERMOSTAT: {
            DD_DEVICE_GROUP: {
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
        },
    },
}


def validate_device_description():
    """Validate the device_description."""
    try:
        return SCHEMA_DEVICE_DESCRIPTION(device_description)
    except Invalid as err:
        _LOGGER.error(
            "The DEVICE_DESCRIPTION could not be validated. %s, %s", err.path, err.msg
        )
        return None


def make_custom_entity(
    device,
    address,
    custom_entity_class,
    device_def: Devices,
    group_base_channels: [int],
):
    """
    Creates custom_entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities = []
    if not group_base_channels:
        group_base_channels = [0]

    entity_desc = _get_device_entities(device_def, group_base_channels[0])

    for base_channel in group_base_channels:
        device_desc = _get_device_group(device_def, base_channel)
        channels = device_desc[DD_PHY_CHANNEL]
        # check if virtual channels should be used
        if device.central.enable_virtual_channels:
            channels.extend(device_desc[DD_VIRT_CHANNEL])
        for channel_no in set(channels):
            entities.extend(
                _create_entities(
                    device=device,
                    address=address,
                    custom_entity_class=custom_entity_class,
                    device_desc=device_desc,
                    entity_desc=entity_desc,
                    channel_no=channel_no,
                )
            )
        # DD_PHY_CHANNEL is empty -> try to create entities based on DD_FIELDS
        if not channels:
            entities.extend(
                _create_entities(
                    device=device,
                    address=address,
                    custom_entity_class=custom_entity_class,
                    device_desc=device_desc,
                    entity_desc=entity_desc,
                    channel_no=None,
                )
            )

    return entities


def _create_entities(
    device,
    address,
    custom_entity_class,
    device_desc,
    entity_desc,
    channel_no,
):
    """Create custom entities."""
    entities = []
    unique_id = generate_unique_id(f"{address}:{channel_no}")
    if unique_id in device.central.hm_entities:
        _LOGGER.debug("make_custom_entity: Skipping %s (already exists)", unique_id)
        return
    entity = custom_entity_class(
        device=device,
        address=address,
        unique_id=unique_id,
        device_desc=device_desc,
        entity_desc=entity_desc,
        channel_no=channel_no,
    )
    if len(entity.data_entities) > 0:
        entity.add_to_collections()
        entities.append(entity)
    return entities


def get_default_entities():
    """Return the default entities."""
    return copy(device_description[DD_DEFAULT_ENTITIES])


def _get_device(device_enum: Devices):
    """Return device from device_descriptions."""
    device = device_description[DD_DEVICES].get(device_enum)
    if device:
        return copy(device)
    return None


def _get_device_group(device_enum: Devices, base_channel_no: int):
    """Return the device group."""
    device = _get_device(device_enum)
    group = {}
    if device:
        group = copy(device[DD_DEVICE_GROUP])
        if group and base_channel_no == 0:
            return group
        if not group:
            return None

    p_channel = group[DD_PHY_CHANNEL]
    group[DD_PHY_CHANNEL] = [x + base_channel_no for x in p_channel]

    v_channel = group[DD_VIRT_CHANNEL]
    if v_channel:
        group[DD_VIRT_CHANNEL] = [x + base_channel_no for x in v_channel]

    fields = group.get(DD_FIELDS)
    if fields:
        new_fields = {}
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
        group[DD_FIELDS] = new_fields
    return group


def _get_device_entities(device_enum: Devices, base_channel_no: int):
    """Return the device entities."""
    additional_entities = (
        device_description[DD_DEVICES]
        .get(device_enum, {})
        .get(DD_ADDITIONAL_ENTITIES, {})
    )
    if additional_entities:
        new_entities = {}
        for channel_no, field in copy(additional_entities).items():
            new_entities[channel_no + base_channel_no] = field
        return new_entities
    return None
