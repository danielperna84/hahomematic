"""
This module contains device descriptions for custom entities.
"""
from __future__ import annotations

from copy import deepcopy
from enum import Enum
import logging
from typing import Any

from voluptuous import All, Invalid, Length, Optional, Required, Schema

import hahomematic.device as hm_device
import hahomematic.entity as hm_entity
from hahomematic.helpers import generate_unique_id

ED_DEFAULT_ENTITIES = "default_entities"
ED_INCLUDE_DEFAULT_ENTITIES = "include_default_entities"
ED_DEVICE_GROUP = "device_group"
ED_DEVICES = "devices"
ED_ADDITIONAL_ENTITIES = "additional_entities"
ED_FIELDS = "fields"
ED_FIELDS_REP = "fields_rep"
ED_PHY_CHANNEL = "phy_channel"
ED_VIRT_CHANNEL = "virt_channel"
DEFAULT_INCLUDE_DEFAULT_ENTITIES = True

FIELD_ACTIVE_PROFILE = "active_profile"
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
FIELD_DOOR_COMMAND = "door_command"
FIELD_DOOR_STATE = "door_state"
FIELD_DUTY_CYCLE = "duty_cycle"
FIELD_DUTYCYCLE = "dutycycle"
FIELD_ENERGY_COUNTER = "energy_counter"
FIELD_FREQUENCY = "frequency"
FIELD_HEATING_COOLING = "heating_cooling"
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
FIELD_OPEN = "open"
FIELD_PARTY_MODE = "party_mode"
FIELD_POWER = "power"
FIELD_RAMP_TIME = "ramp_time"
FIELD_RAMP_TIME_UNIT = "ramp_time_unit"
FIELD_RAMP_TIME_VALUE = "ramp_time_value"
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


class EntityDefinition(Enum):
    """Enum for entity definitions."""

    IP_COVER = "IPCover"
    IP_DIMMER = "IPDimmer"
    IP_GARAGE = "IPGarage"
    IP_SWITCH = "IPSwitch"
    IP_LIGHT_BSL = "IPLightBSL"
    IP_LOCK = "IPLock"
    IP_THERMOSTAT = "IPThermostat"
    IP_THERMOSTAT_GROUP = "IPThermostatGroup"
    RF_COVER = "RfCover"
    RF_DIMMER = "RfDimmer"
    RF_LOCK = "RfLock"
    RF_THERMOSTAT = "RfThermostat"
    RF_THERMOSTAT_GROUP = "RfThermostatGroup"
    SIMPLE_RF_THERMOSTAT = "SimpleRfThermostat"

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)


SCHEMA_ED_FIELD_DETAILS = Schema({Optional(str): str, Optional(str): str})

SCHEMA_ED_FIELD = Schema({Optional(int): SCHEMA_ED_FIELD_DETAILS})

SCHEMA_ED_DEVICE_GROUP = Schema(
    {
        Required(ED_PHY_CHANNEL): All([int], Length(min=1)),
        Required(ED_VIRT_CHANNEL): [int],
        Required(ED_FIELDS_REP, default={}): SCHEMA_ED_FIELD_DETAILS,
        Optional(ED_FIELDS): SCHEMA_ED_FIELD,
    }
)

SCHEMA_ED_DEVICE_GROUPS = Schema(
    {
        Required(ED_DEVICE_GROUP): SCHEMA_ED_DEVICE_GROUP,
        Optional(ED_ADDITIONAL_ENTITIES): SCHEMA_ED_FIELD,
        Optional(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES): bool,
    }
)

SCHEMA_DEVICE_DESCRIPTION = Schema(
    {
        Required(ED_DEFAULT_ENTITIES): SCHEMA_ED_FIELD,
        Required(ED_DEVICES): Schema(
            {
                Required(EntityDefinition): SCHEMA_ED_DEVICE_GROUPS,
            }
        ),
    }
)

entity_definition: dict[str, dict[int | EntityDefinition, Any]] = {
    ED_DEFAULT_ENTITIES: {
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
    ED_DEVICES: {
        EntityDefinition.IP_COVER: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [1],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                        FIELD_CHANNEL_LEVEL_2: "LEVEL_2",
                    },
                },
            },
        },
        EntityDefinition.IP_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [1],
                ED_VIRT_CHANNEL: [2, 3],
                ED_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_RAMP_TIME: "RAMP_TIME",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        EntityDefinition.IP_GARAGE: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_DOOR_COMMAND: "DOOR_COMMAND,",
                    FIELD_DOOR_STATE: "DOOR_STATE",
                },
            },
        },
        EntityDefinition.IP_LIGHT_BSL: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [1],
                ED_VIRT_CHANNEL: [2, 3],
                ED_FIELDS_REP: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_RAMP_TIME_UNIT: "RAMP_TIME_UNIT",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME_VALUE",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_CHANNEL_COLOR: "COLOR",
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        EntityDefinition.IP_SWITCH: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [1],
                ED_VIRT_CHANNEL: [2, 3],
                ED_FIELDS_REP: {
                    FIELD_STATE: "STATE",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_CHANNEL_STATE: "STATE",
                    },
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                4: {
                    FIELD_CURRENT: "CURRENT",
                    FIELD_ENERGY_COUNTER: "ENERGY_COUNTER",
                    FIELD_FREQUENCY: "FREQUENCY",
                    FIELD_POWER: "POWER",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_VOLTAGE: "VOLTAGE",
                },
            },
        },
        EntityDefinition.IP_LOCK: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_LOCK_STATE: "LOCK_STATE",
                    FIELD_LOCK_TARGET_LEVEL: "LOCK_TARGET_LEVEL",
                },
            },
        },
        EntityDefinition.IP_THERMOSTAT: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_ACTIVE_PROFILE: "ACTIVE_PROFILE",
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HEATING_COOLING: "HEATING_COOLING",
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_PARTY_MODE: "PARTY_MODE",
                    FIELD_SETPOINT: "SET_POINT_TEMPERATURE",
                    FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                0: {
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
                8: {
                    FIELD_STATE: "STATE",
                },
            },
        },
        EntityDefinition.IP_THERMOSTAT_GROUP: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_ACTIVE_PROFILE: "ACTIVE_PROFILE",
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HEATING_COOLING: "HEATING_COOLING",
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_PARTY_MODE: "PARTY_MODE",
                    FIELD_SETPOINT: "SET_POINT_TEMPERATURE",
                    FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
            },
            ED_INCLUDE_DEFAULT_ENTITIES: False,
        },
        EntityDefinition.RF_COVER: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
            },
        },
        EntityDefinition.RF_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_RAMP_TIME: "RAMP_TIME",
                },
            },
        },
        EntityDefinition.RF_LOCK: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_OPEN: "OPEN",
                    FIELD_STATE: "STATE",
                },
            },
        },
        EntityDefinition.RF_THERMOSTAT: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_COMFORT_MODE: "COMFORT_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                    FIELD_LOWERING_MODE: "LOWERING_MODE",
                    FIELD_MANU_MODE: "MANU_MODE",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_SETPOINT: "SET_TEMPERATURE",
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                1: {
                    FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                }
            },
        },
        EntityDefinition.RF_THERMOSTAT_GROUP: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_COMFORT_MODE: "COMFORT_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                    FIELD_LOWERING_MODE: "LOWERING_MODE",
                    FIELD_MANU_MODE: "MANU_MODE",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                    FIELD_SETPOINT: "SET_TEMPERATURE",
                },
            },
            ED_INCLUDE_DEFAULT_ENTITIES: False,
        },
        EntityDefinition.SIMPLE_RF_THERMOSTAT: {
            ED_DEVICE_GROUP: {
                ED_PHY_CHANNEL: [0],
                ED_VIRT_CHANNEL: [],
                ED_FIELDS_REP: {},
                ED_FIELDS: {
                    0: {
                        FIELD_HUMIDITY: "HUMIDITY",
                        FIELD_TEMPERATURE: "TEMPERATURE",
                    },
                    1: {
                        FIELD_SETPOINT: "SETPOINT",
                    },
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                1: {FIELD_HUMIDITY: "HUMIDITY", FIELD_TEMPERATURE: "TEMPERATURE"}
            },
        },
    },
}


def validate_entity_definition() -> Any:
    """Validate the entity_definition."""
    try:
        return SCHEMA_DEVICE_DESCRIPTION(entity_definition)
    except Invalid as err:
        _LOGGER.error(
            "The DEVICE_DESCRIPTION could not be validated. %s, %s", err.path, err.msg
        )
        return None


def make_custom_entity(
    device: hm_device.HmDevice,
    device_address: str,
    custom_entity_class: type,
    device_enum: EntityDefinition,
    group_base_channels: list[int],
) -> list[hm_entity.BaseEntity]:
    """
    Creates custom_entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities: list[hm_entity.BaseEntity] = []
    if not group_base_channels:
        group_base_channels = [0]

    entity_def = _get_device_entities(device_enum, group_base_channels[0])

    for base_channel in group_base_channels:
        device_def = _get_device_group(device_enum, base_channel)
        channels = device_def[ED_PHY_CHANNEL]
        # check if virtual channels should be used
        if device.central.option_enable_virtual_channels:
            channels.extend(device_def[ED_VIRT_CHANNEL])
        for channel_no in set(channels):
            entities.extend(
                _create_entities(
                    device=device,
                    device_address=device_address,
                    custom_entity_class=custom_entity_class,
                    device_enum=device_enum,
                    device_def=device_def,
                    entity_def=entity_def,
                    channel_no=channel_no,
                )
            )

    return entities


def _create_entities(
    device: hm_device.HmDevice,
    device_address: str,
    custom_entity_class: type,
    device_enum: EntityDefinition,
    device_def: dict[str, Any],
    entity_def: dict[str, Any],
    channel_no: int | None = None,
) -> list[hm_entity.BaseEntity]:
    """Create custom entities."""
    entities: list[hm_entity.BaseEntity] = []
    unique_id = generate_unique_id(f"{device_address}:{channel_no}")
    if unique_id in device.central.hm_entities:
        _LOGGER.debug("make_custom_entity: Skipping %s (already exists)", unique_id)
        return entities
    entity = custom_entity_class(
        device=device,
        device_address=device_address,
        unique_id=unique_id,
        device_enum=device_enum,
        device_def=device_def,
        entity_def=entity_def,
        channel_no=channel_no,
    )
    if len(entity.data_entities) > 0:
        entity.add_to_collections()
        entities.append(entity)
    return entities


def get_default_entities() -> dict[str, Any]:
    """Return the default entities."""
    return deepcopy(entity_definition[ED_DEFAULT_ENTITIES])  # type: ignore[arg-type]


def get_include_default_entities(device_enum: EntityDefinition) -> bool:
    """Return if default entities should be included."""
    device = _get_device(device_enum)
    if device:
        return device.get(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES)
    return DEFAULT_INCLUDE_DEFAULT_ENTITIES


def _get_device(device_enum: EntityDefinition) -> dict[str, Any] | None:
    """Return device from entity definitions."""
    device = entity_definition[ED_DEVICES].get(device_enum)
    if device:
        return deepcopy(device)  # type: ignore[no-any-return]
    return None


def _get_device_group(
    device_enum: EntityDefinition, base_channel_no: int
) -> dict[str, Any]:
    """Return the device group."""
    device = _get_device(device_enum)
    group: dict[str, Any] = {}
    if device:
        group = deepcopy(device[ED_DEVICE_GROUP])
        if group and base_channel_no == 0:
            return group
        if not group:
            return {}

    p_channel = group[ED_PHY_CHANNEL]
    group[ED_PHY_CHANNEL] = [x + base_channel_no for x in p_channel]

    v_channel = group[ED_VIRT_CHANNEL]
    if v_channel:
        group[ED_VIRT_CHANNEL] = [x + base_channel_no for x in v_channel]

    fields = group.get(ED_FIELDS)
    if fields:
        new_fields = {}
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
        group[ED_FIELDS] = new_fields
    return group


def _get_device_entities(
    device_enum: EntityDefinition, base_channel_no: int
) -> dict[str, Any]:
    """Return the device entities."""
    additional_entities = (
        entity_definition[ED_DEVICES]
        .get(device_enum, {})
        .get(ED_ADDITIONAL_ENTITIES, {})
    )
    new_entities: dict[str, Any] = {}
    if additional_entities:
        for channel_no, field in deepcopy(additional_entities).items():
            new_entities[channel_no + base_channel_no] = field
    return new_entities
