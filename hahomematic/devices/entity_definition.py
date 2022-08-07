"""
This module contains device descriptions for custom entities.
"""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any

from voluptuous import Invalid, Optional, Required, Schema

from hahomematic.backport import StrEnum
import hahomematic.device as hm_device
import hahomematic.entity as hm_entity
from hahomematic.helpers import generate_unique_identifier

ED_DEFAULT_ENTITIES = "default_entities"
ED_INCLUDE_DEFAULT_ENTITIES = "include_default_entities"
ED_DEVICE_GROUP = "device_group"
ED_DEVICE_DEFINITIONS = "device_definitions"
ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE = "additional_entities_by_device_type"
ED_ADDITIONAL_ENTITIES = "additional_entities"
ED_FIELDS = "fields"
ED_REPEATABLE_FIELDS = "repeatable_fields"
ED_VISIBLE_REPEATABLE_FIELDS = "visible_repeatable_fields"
ED_PRIMARY_CHANNEL = "primary_channel"
ED_SECONDARY_CHANNELS = "secondary_channels"
ED_VISIBLE_FIELDS = "visible_fields"
DEFAULT_INCLUDE_DEFAULT_ENTITIES = True

FIELD_ACTIVE_PROFILE = "active_profile"
FIELD_AUTO_MODE = "auto_mode"
FIELD_BOOST_MODE = "boost_mode"
FIELD_CHANNEL_COLOR = "channel_color"
FIELD_CHANNEL_LEVEL = "channel_level"
FIELD_CHANNEL_LEVEL_2 = "channel_level_2"
FIELD_CHANNEL_STATE = "channel_state"
FIELD_COLOR = "color"
FIELD_COLOR_LEVEL = "color_temp"
FIELD_COMFORT_MODE = "comfort_mode"
FIELD_CONTROL_MODE = "control_mode"
FIELD_CURRENT = "current"
FIELD_DIRECTION = "direction"
FIELD_DOOR_COMMAND = "door_command"
FIELD_DOOR_STATE = "door_state"
FIELD_DUTY_CYCLE = "duty_cycle"
FIELD_DUTYCYCLE = "dutycycle"
FIELD_ERROR = "error"
FIELD_ENERGY_COUNTER = "energy_counter"
FIELD_FREQUENCY = "frequency"
FIELD_HEATING_COOLING = "heating_cooling"
FIELD_HUMIDITY = "humidity"
FIELD_INHIBIT = "inhibit"
FIELD_LEVEL = "level"
FIELD_LEVEL_2 = "level_2"
FIELD_LOCK_STATE = "lock_state"
FIELD_LOCK_TARGET_LEVEL = "lock_target_level"
FIELD_LOW_BAT = "low_bat"
FIELD_LOWBAT = "lowbat"
FIELD_LOWERING_MODE = "lowering_mode"
FIELD_MANU_MODE = "manu_mode"
FIELD_ON_TIME_VALUE = "on_time_value"
FIELD_ON_TIME_UNIT = "on_time_unit"
FIELD_OPERATING_VOLTAGE = "operating_voltage"
FIELD_OPEN = "open"
FIELD_PARTY_MODE = "party_mode"
FIELD_PROGRAM = "program"
FIELD_POWER = "power"
FIELD_RAMP_TIME_VALUE = "ramp_time_value"
FIELD_RAMP_TIME_UNIT = "ramp_time_unit"
FIELD_RSSI_DEVICE = "rssi_device"
FIELD_RSSI_PEER = "rssi_peer"
FIELD_SABOTAGE = "sabotage"
FIELD_SECTION = "section"
FIELD_SET_POINT_MODE = "set_point_mode"
FIELD_SETPOINT = "setpoint"
FIELD_STATE = "state"
FIELD_STOP = "stop"
FIELD_SWITCH_MAIN = "switch_main"
FIELD_SWITCH_V1 = "vswitch_1"
FIELD_SWITCH_V2 = "vswitch_2"
FIELD_TEMPERATURE = "temperature"
FIELD_VALVE_STATE = "valve_state"
FIELD_VOLTAGE = "voltage"

FIELD_ACOUSTIC_ALARM_ACTIVE = "acoustic_alarm_active"
FIELD_ACOUSTIC_ALARM_SELECTION = "acoustic_alarm_selection"
FIELD_OPTICAL_ALARM_ACTIVE = "optical_alarm_active"
FIELD_OPTICAL_ALARM_SELECTION = "optical_alarm_selection"

_LOGGER = logging.getLogger(__name__)


class EntityDefinition(StrEnum):
    """Enum for entity definitions."""

    IP_COVER = "IPCover"
    IP_DIMMER = "IPDimmer"
    IP_GARAGE = "IPGarage"
    IP_SWITCH = "IPSwitch"
    IP_FIXED_COLOR_LIGHT = "IPFixedColorLight"
    IP_SIMPLE_FIXED_COLOR_LIGHT = "IPSimpleFixedColorLight"
    IP_LOCK = "IPLock"
    IP_THERMOSTAT = "IPThermostat"
    IP_THERMOSTAT_GROUP = "IPThermostatGroup"
    IP_SIREN = "IPSiren"
    RF_COVER = "RfCover"
    RF_DIMMER = "RfDimmer"
    RF_DIMMER_COLOR = "RfDimmer_Color"
    RF_DIMMER_COLOR_TEMP = "RfDimmer_Color_Temp"
    RF_DIMMER_WITH_VIRT_CHANNEL = "RfDimmerWithVirtChannel"
    RF_LOCK = "RfLock"
    RF_THERMOSTAT = "RfThermostat"
    RF_THERMOSTAT_GROUP = "RfThermostatGroup"
    RF_SIREN = "RfSiren"
    RF_SWITCH = "RfSwitch"
    SIMPLE_RF_THERMOSTAT = "SimpleRfThermostat"


SCHEMA_ED_ADDITIONAL_ENTITIES = Schema({Required(int): Schema({Optional(str)})})

SCHEMA_ED_FIELD_DETAILS = Schema({Required(str): str})

SCHEMA_ED_FIELD = Schema({Required(int): SCHEMA_ED_FIELD_DETAILS})

SCHEMA_ED_DEVICE_GROUP = Schema(
    {
        Required(ED_PRIMARY_CHANNEL): int,
        Optional(ED_SECONDARY_CHANNELS): [int],
        Optional(ED_REPEATABLE_FIELDS): SCHEMA_ED_FIELD_DETAILS,
        Optional(ED_VISIBLE_REPEATABLE_FIELDS): SCHEMA_ED_FIELD_DETAILS,
        Optional(ED_FIELDS): SCHEMA_ED_FIELD,
        Optional(ED_VISIBLE_FIELDS): SCHEMA_ED_FIELD,
    }
)

SCHEMA_ED_DEVICE_GROUPS = Schema(
    {
        Required(ED_DEVICE_GROUP): SCHEMA_ED_DEVICE_GROUP,
        Optional(ED_ADDITIONAL_ENTITIES): SCHEMA_ED_ADDITIONAL_ENTITIES,
        Optional(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES): bool,
    }
)

SCHEMA_DEVICE_DESCRIPTION = Schema(
    {
        Required(ED_DEFAULT_ENTITIES): SCHEMA_ED_ADDITIONAL_ENTITIES,
        Required(ED_DEVICE_DEFINITIONS): Schema(
            {
                Required(EntityDefinition): SCHEMA_ED_DEVICE_GROUPS,
            }
        ),
        Required(ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE): Schema(
            {
                Required(str): SCHEMA_ED_ADDITIONAL_ENTITIES,
            }
        ),
    }
)

entity_definition: dict[str, dict[int | str | EntityDefinition, Any]] = {
    ED_DEFAULT_ENTITIES: {
        0: {
            "DUTY_CYCLE",
            "DUTYCYCLE",
            "LOW_BAT",
            "LOWBAT",
            "OPERATING_VOLTAGE",
            "RSSI_DEVICE",
            "RSSI_PEER",
            "SABOTAGE",
        },
        2: {
            "BATTERY_STATE",
        },
        4: {
            "BATTERY_STATE",
        },
    },
    ED_DEVICE_DEFINITIONS: {
        EntityDefinition.IP_COVER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_DIRECTION: "ACTIVITY_STATE",
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                        FIELD_CHANNEL_LEVEL_2: "LEVEL_2",
                    },
                },
            },
        },
        EntityDefinition.IP_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: [2, 3],
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
                ED_VISIBLE_FIELDS: {
                    0: {
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        EntityDefinition.IP_GARAGE: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_DOOR_COMMAND: "DOOR_COMMAND",
                    FIELD_SECTION: "SECTION",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_DOOR_STATE: "DOOR_STATE",
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                1: {
                    "STATE",
                },
            },
        },
        EntityDefinition.IP_FIXED_COLOR_LIGHT: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: [2, 3],
                ED_REPEATABLE_FIELDS: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_UNIT: "DURATION_UNIT",
                    FIELD_ON_TIME_VALUE: "DURATION_VALUE",
                    FIELD_RAMP_TIME_UNIT: "RAMP_TIME_UNIT",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME_VALUE",
                },
                ED_VISIBLE_FIELDS: {
                    0: {
                        FIELD_CHANNEL_COLOR: "COLOR",
                        FIELD_CHANNEL_LEVEL: "LEVEL",
                    },
                },
            },
        },
        EntityDefinition.IP_SIMPLE_FIXED_COLOR_LIGHT: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_COLOR: "COLOR",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_UNIT: "DURATION_UNIT",
                    FIELD_ON_TIME_VALUE: "DURATION_VALUE",
                    FIELD_RAMP_TIME_UNIT: "RAMP_TIME_UNIT",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME_VALUE",
                },
            },
        },
        EntityDefinition.IP_SWITCH: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: [2, 3],
                ED_REPEATABLE_FIELDS: {
                    FIELD_STATE: "STATE",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                },
                ED_VISIBLE_FIELDS: {
                    0: {
                        FIELD_CHANNEL_STATE: "STATE",
                    },
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                4: {
                    "CURRENT",
                    "ENERGY_COUNTER",
                    "FREQUENCY",
                    "POWER",
                    "ACTUAL_TEMPERATURE",
                    "VOLTAGE",
                },
            },
        },
        EntityDefinition.IP_LOCK: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_REPEATABLE_FIELDS: {
                    FIELD_DIRECTION: "ACTIVITY_STATE",
                    FIELD_LOCK_STATE: "LOCK_STATE",
                    FIELD_LOCK_TARGET_LEVEL: "LOCK_TARGET_LEVEL",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_ERROR: "ERROR_JAMMED",
                    },
                },
            },
        },
        EntityDefinition.IP_SIREN: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 3,
                ED_REPEATABLE_FIELDS: {
                    FIELD_ACOUSTIC_ALARM_ACTIVE: "ACOUSTIC_ALARM_ACTIVE",
                    FIELD_OPTICAL_ALARM_ACTIVE: "OPTICAL_ALARM_ACTIVE",
                    FIELD_ACOUSTIC_ALARM_SELECTION: "ACOUSTIC_ALARM_SELECTION",
                    FIELD_OPTICAL_ALARM_SELECTION: "OPTICAL_ALARM_SELECTION",
                },
            },
        },
        EntityDefinition.IP_THERMOSTAT: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_ACTIVE_PROFILE: "ACTIVE_PROFILE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HEATING_COOLING: "HEATING_COOLING",
                    FIELD_PARTY_MODE: "PARTY_MODE",
                    FIELD_SETPOINT: "SET_POINT_TEMPERATURE",
                    FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
                ED_VISIBLE_FIELDS: {
                    0: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    8: {
                        FIELD_STATE: "STATE",
                    },
                },
            },
        },
        EntityDefinition.IP_THERMOSTAT_GROUP: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_ACTIVE_PROFILE: "ACTIVE_PROFILE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_HEATING_COOLING: "HEATING_COOLING",
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_PARTY_MODE: "PARTY_MODE",
                    FIELD_SETPOINT: "SET_POINT_TEMPERATURE",
                    FIELD_SET_POINT_MODE: "SET_POINT_MODE",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_LEVEL: "LEVEL",
                    },
                    3: {
                        FIELD_STATE: "STATE",
                    },
                },
            },
            ED_INCLUDE_DEFAULT_ENTITIES: False,
        },
        EntityDefinition.RF_COVER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_DIRECTION: "DIRECTION",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_2",
                    FIELD_STOP: "STOP",
                },
            },
        },
        EntityDefinition.RF_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
            },
        },
        EntityDefinition.RF_DIMMER_COLOR: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
                ED_FIELDS: {
                    1: {
                        FIELD_COLOR: "COLOR",
                    },
                    2: {
                        FIELD_PROGRAM: "PROGRAM",
                    },
                },
            },
        },
        EntityDefinition.RF_DIMMER_COLOR_TEMP: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
                ED_FIELDS: {
                    1: {
                        FIELD_COLOR_LEVEL: "LEVEL",
                    },
                },
            },
        },
        EntityDefinition.RF_DIMMER_WITH_VIRT_CHANNEL: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_SECONDARY_CHANNELS: [1, 2],
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
            },
        },
        EntityDefinition.RF_LOCK: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_DIRECTION: "DIRECTION",
                    FIELD_OPEN: "OPEN",
                    FIELD_STATE: "STATE",
                    FIELD_ERROR: "ERROR",
                },
            },
        },
        EntityDefinition.RF_SWITCH: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_STATE: "STATE",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                1: {
                    "CURRENT",
                    "ENERGY_COUNTER",
                    "FREQUENCY",
                    "POWER",
                    "VOLTAGE",
                },
            },
        },
        EntityDefinition.RF_THERMOSTAT: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_AUTO_MODE: "AUTO_MODE",
                    FIELD_BOOST_MODE: "BOOST_MODE",
                    FIELD_COMFORT_MODE: "COMFORT_MODE",
                    FIELD_CONTROL_MODE: "CONTROL_MODE",
                    FIELD_LOWERING_MODE: "LOWERING_MODE",
                    FIELD_MANU_MODE: "MANU_MODE",
                    FIELD_SETPOINT: "SET_TEMPERATURE",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
                ED_VISIBLE_FIELDS: {
                    0: {
                        FIELD_VALVE_STATE: "VALVE_STATE",
                    },
                },
            },
        },
        EntityDefinition.RF_THERMOSTAT_GROUP: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
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
                ED_PRIMARY_CHANNEL: 0,
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_HUMIDITY: "HUMIDITY",
                    FIELD_TEMPERATURE: "TEMPERATURE",
                },
                ED_FIELDS: {
                    1: {
                        FIELD_SETPOINT: "SETPOINT",
                    },
                },
            },
        },
    },
    ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE: {
        "HmIP-SCTH230": {
            1: {
                "CONCENTRATION",
            },
            4: {
                "HUMIDITY",
                "ACTUAL_TEMPERATURE",
            },
        },
        "HmIP-DLD": {
            0: {
                "ERROR_JAMMED",
            },
        },
        # HM-Sec-Win*
        "HM-Sec-Win": {
            1: {
                "DIRECTION",
                "WORKING",
                "ERROR",
            },
            2: {
                "LEVEL",
                "STATUS",
            },
        },
        # HM-Sec-Key*
        "HM-Sec-Key": {
            1: {
                "DIRECTION",
                "ERROR",
            },
        },
        # HmIPW-DR*
        "HmIPW-DR": {
            0: {
                "ACTUAL_TEMPERATURE",
            },
        },
        # HmIP-DR*
        "HmIP-DR": {
            0: {
                "ACTUAL_TEMPERATURE",
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
        channels = [device_def[ED_PRIMARY_CHANNEL]]
        if secondary_channels := device_def.get(ED_SECONDARY_CHANNELS):
            channels.extend(secondary_channels)
        for channel_no in set(channels):
            entities.extend(
                _create_entities(
                    device=device,
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
    custom_entity_class: type,
    device_enum: EntityDefinition,
    device_def: dict[str, Any],
    entity_def: dict[int, set[str]],
    channel_no: int | None = None,
) -> list[hm_entity.BaseEntity]:
    """Create custom entities."""
    entities: list[hm_entity.BaseEntity] = []
    unique_identifier = generate_unique_identifier(
        central=device.central, address=f"{device.device_address}:{channel_no}"
    )
    if unique_identifier in device.central.hm_entities:
        _LOGGER.debug(
            "make_custom_entity: Skipping %s (already exists)", unique_identifier
        )
        return entities
    if f"{device.device_address}:{channel_no}" not in device.channels:
        return entities
    entity = custom_entity_class(
        device=device,
        unique_identifier=unique_identifier,
        device_enum=device_enum,
        device_def=device_def,
        entity_def=entity_def,
        channel_no=channel_no,
    )
    if len(entity.data_entities) > 0:
        entity.add_to_collections()
        entities.append(entity)
    return entities


def get_default_entities() -> dict[int, set[str]]:
    """Return the default entities."""
    return deepcopy(entity_definition[ED_DEFAULT_ENTITIES])  # type: ignore[arg-type]


def get_additional_entities_by_device_type(device_type: str) -> dict[int, set[str]]:
    """Return the additional entities."""
    for data in entity_definition[ED_ADDITIONAL_ENTITIES_BY_DEVICE_TYPE].items():
        device: str = str(data[0])
        additional_entities: dict[int, set[str]] = data[1]
        if device_type.startswith(device):
            return deepcopy(additional_entities)
    return {}


def get_include_default_entities(device_enum: EntityDefinition) -> bool:
    """Return if default entities should be included."""
    device = _get_device(device_enum)
    if device:
        return device.get(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES)
    return DEFAULT_INCLUDE_DEFAULT_ENTITIES


def _get_device(device_enum: EntityDefinition) -> dict[str, Any] | None:
    """Return device from entity definitions."""
    device = entity_definition[ED_DEVICE_DEFINITIONS].get(device_enum)
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

    # Add base_channel_no to the primary_channel to get the real primary_channel number
    primary_channel = group[ED_PRIMARY_CHANNEL]
    group[ED_PRIMARY_CHANNEL] = primary_channel + base_channel_no

    # Add base_channel_no to the secondary_channels to get the real secondary_channel numbers
    if secondary_channel := group.get(ED_SECONDARY_CHANNELS):
        group[ED_SECONDARY_CHANNELS] = [x + base_channel_no for x in secondary_channel]

    group[ED_VISIBLE_FIELDS] = _rebase_entity_dict(
        entity_dict=ED_VISIBLE_FIELDS, group=group, base_channel_no=base_channel_no
    )
    group[ED_FIELDS] = _rebase_entity_dict(
        entity_dict=ED_FIELDS, group=group, base_channel_no=base_channel_no
    )
    return group


def _rebase_entity_dict(
    entity_dict: str, group: dict[str, Any], base_channel_no: int
) -> dict[int, Any]:
    """Rebase entity_dict with base_channel_no."""
    new_fields = {}
    if fields := group.get(entity_dict):
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
    return new_fields


def _get_device_entities(
    device_enum: EntityDefinition, base_channel_no: int
) -> dict[int, set[str]]:
    """Return the device entities."""
    additional_entities = (
        entity_definition[ED_DEVICE_DEFINITIONS]
        .get(device_enum, {})
        .get(ED_ADDITIONAL_ENTITIES, {})
    )
    new_entities: dict[int, set[str]] = {}
    if additional_entities:
        for channel_no, field in deepcopy(additional_entities).items():
            new_entities[channel_no + base_channel_no] = field
    return new_entities
