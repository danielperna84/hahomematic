"""The module contains device descriptions for custom entities."""
from __future__ import annotations

from copy import deepcopy
import logging
from typing import Any, Final, cast

import voluptuous as vol

from hahomematic import support as hm_support
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import entity as hmce
from hahomematic.platforms.custom.const import (
    FIELD_ACOUSTIC_ALARM_ACTIVE,
    FIELD_ACOUSTIC_ALARM_SELECTION,
    FIELD_ACTIVE_PROFILE,
    FIELD_AUTO_MODE,
    FIELD_BOOST_MODE,
    FIELD_CHANNEL_COLOR,
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_LEVEL_2,
    FIELD_CHANNEL_OPERATION_MODE,
    FIELD_CHANNEL_STATE,
    FIELD_COLOR,
    FIELD_COLOR_LEVEL,
    FIELD_COMFORT_MODE,
    FIELD_CONTROL_MODE,
    FIELD_DIRECTION,
    FIELD_DOOR_COMMAND,
    FIELD_DOOR_STATE,
    FIELD_DURATION,
    FIELD_DURATION_UNIT,
    FIELD_ERROR,
    FIELD_HEATING_COOLING,
    FIELD_HUMIDITY,
    FIELD_LEVEL,
    FIELD_LEVEL_2,
    FIELD_LOCK_STATE,
    FIELD_LOCK_TARGET_LEVEL,
    FIELD_LOWERING_MODE,
    FIELD_MANU_MODE,
    FIELD_ON_TIME_UNIT,
    FIELD_ON_TIME_VALUE,
    FIELD_OPEN,
    FIELD_OPTICAL_ALARM_ACTIVE,
    FIELD_OPTICAL_ALARM_SELECTION,
    FIELD_PARTY_MODE,
    FIELD_PROGRAM,
    FIELD_RAMP_TIME_UNIT,
    FIELD_RAMP_TIME_VALUE,
    FIELD_SECTION,
    FIELD_SET_POINT_MODE,
    FIELD_SETPOINT,
    FIELD_SMOKE_DETECTOR_ALARM_STATUS,
    FIELD_SMOKE_DETECTOR_COMMAND,
    FIELD_STATE,
    FIELD_STOP,
    FIELD_TEMPERATURE,
    FIELD_TEMPERATURE_MAXIMUM,
    FIELD_TEMPERATURE_MINIMUM,
    FIELD_VALVE_STATE,
    HmEntityDefinition,
)
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.support import generate_unique_identifier

ED_DEFAULT_ENTITIES: Final = "default_entities"
ED_INCLUDE_DEFAULT_ENTITIES: Final = "include_default_entities"
ED_DEVICE_GROUP: Final = "device_group"
ED_DEVICE_DEFINITIONS: Final = "device_definitions"
ED_ADDITIONAL_ENTITIES: Final = "additional_entities"
ED_FIELDS: Final = "fields"
ED_REPEATABLE_FIELDS: Final = "repeatable_fields"
ED_VISIBLE_REPEATABLE_FIELDS: Final = "visible_repeatable_fields"
ED_PRIMARY_CHANNEL: Final = "primary_channel"
ED_SECONDARY_CHANNELS: Final = "secondary_channels"
ED_VISIBLE_FIELDS: Final = "visible_fields"
DEFAULT_INCLUDE_DEFAULT_ENTITIES: Final = True

ALL_DEVICES: list[dict[str, CustomConfig | tuple[CustomConfig, ...]]] = []
ALL_BLACKLISTED_DEVICES: list[tuple[str, ...]] = []

_LOGGER = logging.getLogger(__name__)

SCHEMA_ED_ADDITIONAL_ENTITIES = vol.Schema(
    {vol.Required(vol.Any(int, tuple[int, ...])): vol.Schema((vol.Optional(str),))}
)

SCHEMA_ED_FIELD_DETAILS = vol.Schema({vol.Required(str): str})

SCHEMA_ED_FIELD = vol.Schema({vol.Required(int): SCHEMA_ED_FIELD_DETAILS})

SCHEMA_ED_DEVICE_GROUP = vol.Schema(
    {
        vol.Required(ED_PRIMARY_CHANNEL): int,
        vol.Optional(ED_SECONDARY_CHANNELS): (int,),
        vol.Optional(ED_REPEATABLE_FIELDS): SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED_VISIBLE_REPEATABLE_FIELDS): SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED_FIELDS): SCHEMA_ED_FIELD,
        vol.Optional(ED_VISIBLE_FIELDS): SCHEMA_ED_FIELD,
    }
)

SCHEMA_ED_DEVICE_GROUPS = vol.Schema(
    {
        vol.Required(ED_DEVICE_GROUP): SCHEMA_ED_DEVICE_GROUP,
        vol.Optional(ED_ADDITIONAL_ENTITIES): SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Optional(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES): bool,
    }
)

SCHEMA_DEVICE_DESCRIPTION = vol.Schema(
    {
        vol.Required(ED_DEFAULT_ENTITIES): SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Required(ED_DEVICE_DEFINITIONS): vol.Schema(
            {
                vol.Required(HmEntityDefinition): SCHEMA_ED_DEVICE_GROUPS,
            }
        ),
    }
)

entity_definition: dict[str, dict[int | str | HmEntityDefinition, vol.Any]] = {
    ED_DEFAULT_ENTITIES: {
        0: (
            "DUTY_CYCLE",
            "DUTYCYCLE",
            "LOW_BAT",
            "LOWBAT",
            "OPERATING_VOLTAGE",
            "RSSI_DEVICE",
            "RSSI_PEER",
            "SABOTAGE",
        ),
        2: ("BATTERY_STATE",),
        4: ("BATTERY_STATE",),
    },
    ED_DEVICE_DEFINITIONS: {
        HmEntityDefinition.IP_COVER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: (2, 3),
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
                        FIELD_CHANNEL_OPERATION_MODE: "CHANNEL_OPERATION_MODE",
                    },
                },
            },
        },
        HmEntityDefinition.IP_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: (2, 3),
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
        HmEntityDefinition.IP_GARAGE: {
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
                1: ("STATE",),
            },
        },
        HmEntityDefinition.IP_FIXED_COLOR_LIGHT: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: (2, 3),
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
        HmEntityDefinition.IP_SIMPLE_FIXED_COLOR_LIGHT: {
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
        HmEntityDefinition.IP_SWITCH: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_SECONDARY_CHANNELS: (2, 3),
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
                4: (
                    "CURRENT",
                    "ENERGY_COUNTER",
                    "FREQUENCY",
                    "POWER",
                    "ACTUAL_TEMPERATURE",
                    "VOLTAGE",
                ),
            },
        },
        HmEntityDefinition.IP_LOCK: {
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
        HmEntityDefinition.IP_SIREN: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 3,
                ED_REPEATABLE_FIELDS: {
                    FIELD_ACOUSTIC_ALARM_ACTIVE: "ACOUSTIC_ALARM_ACTIVE",
                    FIELD_OPTICAL_ALARM_ACTIVE: "OPTICAL_ALARM_ACTIVE",
                    FIELD_ACOUSTIC_ALARM_SELECTION: "ACOUSTIC_ALARM_SELECTION",
                    FIELD_OPTICAL_ALARM_SELECTION: "OPTICAL_ALARM_SELECTION",
                    FIELD_DURATION: "DURATION_VALUE",
                    FIELD_DURATION_UNIT: "DURATION_UNIT",
                },
            },
        },
        HmEntityDefinition.IP_SIREN_SMOKE: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 1,
                ED_REPEATABLE_FIELDS: {
                    FIELD_SMOKE_DETECTOR_COMMAND: "SMOKE_DETECTOR_COMMAND",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_SMOKE_DETECTOR_ALARM_STATUS: "SMOKE_DETECTOR_ALARM_STATUS",
                },
            },
        },
        HmEntityDefinition.IP_THERMOSTAT: {
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
                    FIELD_TEMPERATURE_MAXIMUM: "TEMPERATURE_MAXIMUM",
                    FIELD_TEMPERATURE_MINIMUM: "TEMPERATURE_MINIMUM",
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
        HmEntityDefinition.IP_THERMOSTAT_GROUP: {
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
                    FIELD_TEMPERATURE_MAXIMUM: "TEMPERATURE_MAXIMUM",
                    FIELD_TEMPERATURE_MINIMUM: "TEMPERATURE_MINIMUM",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_HUMIDITY: "HUMIDITY",
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
        HmEntityDefinition.RF_COVER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_DIRECTION: "DIRECTION",
                    FIELD_LEVEL: "LEVEL",
                    FIELD_LEVEL_2: "LEVEL_SLATS",
                    FIELD_STOP: "STOP",
                },
            },
        },
        HmEntityDefinition.RF_DIMMER: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
            },
        },
        HmEntityDefinition.RF_DIMMER_COLOR: {
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
        HmEntityDefinition.RF_DIMMER_COLOR_TEMP: {
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
        HmEntityDefinition.RF_DIMMER_WITH_VIRT_CHANNEL: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_SECONDARY_CHANNELS: (1, 2),
                ED_REPEATABLE_FIELDS: {
                    FIELD_LEVEL: "LEVEL",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                    FIELD_RAMP_TIME_VALUE: "RAMP_TIME",
                },
            },
        },
        HmEntityDefinition.RF_LOCK: {
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
        HmEntityDefinition.RF_SWITCH: {
            ED_DEVICE_GROUP: {
                ED_PRIMARY_CHANNEL: 0,
                ED_REPEATABLE_FIELDS: {
                    FIELD_STATE: "STATE",
                    FIELD_ON_TIME_VALUE: "ON_TIME",
                },
            },
            ED_ADDITIONAL_ENTITIES: {
                1: (
                    "CURRENT",
                    "ENERGY_COUNTER",
                    "FREQUENCY",
                    "POWER",
                    "VOLTAGE",
                ),
            },
        },
        HmEntityDefinition.RF_THERMOSTAT: {
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
                    FIELD_TEMPERATURE_MAXIMUM: "TEMPERATURE_MAXIMUM",
                    FIELD_TEMPERATURE_MINIMUM: "TEMPERATURE_MINIMUM",
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
        HmEntityDefinition.RF_THERMOSTAT_GROUP: {
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
                    FIELD_TEMPERATURE_MAXIMUM: "TEMPERATURE_MAXIMUM",
                    FIELD_TEMPERATURE_MINIMUM: "TEMPERATURE_MINIMUM",
                },
                ED_VISIBLE_REPEATABLE_FIELDS: {
                    FIELD_HUMIDITY: "ACTUAL_HUMIDITY",
                    FIELD_TEMPERATURE: "ACTUAL_TEMPERATURE",
                },
                ED_FIELDS: {
                    0: {
                        FIELD_VALVE_STATE: "VALVE_STATE",
                    },
                },
            },
            ED_INCLUDE_DEFAULT_ENTITIES: False,
        },
        HmEntityDefinition.SIMPLE_RF_THERMOSTAT: {
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
}


def validate_entity_definition() -> Any:
    """Validate the entity_definition."""
    try:
        return SCHEMA_DEVICE_DESCRIPTION(entity_definition)
    except vol.Invalid as err:  # pragma: no cover
        _LOGGER.error("The entity definition could not be validated. %s, %s", err.path, err.msg)
        return None


def make_custom_entity(
    device: hmd.HmDevice,
    custom_entity_class: type,
    device_enum: HmEntityDefinition,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hmce.CustomEntity, ...]:
    """
    Create custom_entities.

    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities: list[hmce.CustomEntity] = []

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
                    extended=extended,
                )
            )

    return tuple(entities)


def _create_entities(
    device: hmd.HmDevice,
    custom_entity_class: type,
    device_enum: HmEntityDefinition,
    device_def: dict[str, vol.Any],
    entity_def: dict[int, tuple[str, ...]],
    channel_no: int | None = None,
    extended: ExtendedConfig | None = None,
) -> tuple[hmce.CustomEntity, ...]:
    """Create custom entities."""
    entities: list[hmce.CustomEntity] = []
    channel_address = hm_support.get_channel_address(
        device_address=device.device_address, channel_no=channel_no
    )
    unique_identifier = generate_unique_identifier(central=device.central, address=channel_address)
    if channel_address not in device.channels:
        return tuple(entities)
    entity = custom_entity_class(
        device=device,
        unique_identifier=unique_identifier,
        device_enum=device_enum,
        device_def=device_def,
        entity_def=entity_def,
        channel_no=channel_no,
        extended=extended,
    )
    if len(entity.data_entities) > 0:
        device.add_entity(entity)
        entities.append(entity)
    return tuple(entities)


def get_default_entities() -> dict[int | tuple[int, ...], tuple[str, ...]]:
    """Return the default entities."""
    return deepcopy(entity_definition[ED_DEFAULT_ENTITIES])  # type: ignore[arg-type]


def get_include_default_entities(device_enum: HmEntityDefinition) -> bool:
    """Return if default entities should be included."""
    device = _get_device_definition(device_enum)
    return device.get(ED_INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES)


def _get_device_definition(device_enum: HmEntityDefinition) -> dict[str, vol.Any]:
    """Return device from entity definitions."""
    return cast(
        dict[str, vol.Any], deepcopy(entity_definition[ED_DEVICE_DEFINITIONS][device_enum])
    )


def _get_device_group(device_enum: HmEntityDefinition, base_channel_no: int) -> dict[str, vol.Any]:
    """Return the device group."""
    device = _get_device_definition(device_enum)
    group = cast(dict[str, vol.Any], deepcopy(device[ED_DEVICE_GROUP]))
    if group and base_channel_no == 0:
        return group

    # Add base_channel_no to the primary_channel to get the real primary_channel number
    primary_channel = group[ED_PRIMARY_CHANNEL]
    group[ED_PRIMARY_CHANNEL] = primary_channel + base_channel_no

    # Add base_channel_no to the secondary_channels
    # to get the real secondary_channel numbers
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
    entity_dict: str, group: dict[str, vol.Any], base_channel_no: int
) -> dict[int, vol.Any]:
    """Rebase entity_dict with base_channel_no."""
    new_fields = {}
    if fields := group.get(entity_dict):
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
    return new_fields


def _get_device_entities(
    device_enum: HmEntityDefinition, base_channel_no: int
) -> dict[int, tuple[str, ...]]:
    """Return the device entities."""
    additional_entities = (
        entity_definition[ED_DEVICE_DEFINITIONS]
        .get(device_enum, {})
        .get(ED_ADDITIONAL_ENTITIES, {})
    )
    new_entities: dict[int, tuple[str, ...]] = {}
    if additional_entities:
        for channel_no, field in deepcopy(additional_entities).items():
            new_entities[channel_no + base_channel_no] = field
    return new_entities


def get_entity_configs(
    device_type: str,
) -> list[CustomConfig | tuple[CustomConfig, ...]]:
    """Return the entity configs to create custom entities."""
    device_type = device_type.lower().replace("hb-", "hm-")
    funcs = []
    for platform_blacklisted_devices in ALL_BLACKLISTED_DEVICES:
        if hm_support.element_matches_key(
            search_elements=platform_blacklisted_devices,
            compare_with=device_type,
        ):
            return []

    for platform_devices in ALL_DEVICES:
        if func := _get_entity_config_by_platform(
            platform_devices=platform_devices,
            device_type=device_type,
        ):
            funcs.append(func)
    return funcs


def _get_entity_config_by_platform(
    platform_devices: dict[str, CustomConfig | tuple[CustomConfig, ...]],
    device_type: str,
) -> CustomConfig | tuple[CustomConfig, ...] | None:
    """Return the entity configs to create custom entities."""
    for d_type, custom_configs in platform_devices.items():
        if device_type.lower() == d_type.lower():
            return custom_configs

    for d_type, custom_configs in platform_devices.items():
        if device_type.lower().startswith(d_type.lower()):
            return custom_configs

    return None


def is_multi_channel_device(device_type: str) -> bool:
    """Return true, if device has multiple channels."""
    channels: list[int] = []
    for entity_configs in get_entity_configs(device_type=device_type):
        if isinstance(entity_configs, CustomConfig):
            channels.extend(entity_configs.channels)
        else:
            for entity_config in entity_configs:
                channels.extend(entity_config.channels)

    return len(channels) > 1


def entity_definition_exists(device_type: str) -> bool:
    """Check if device desc exits."""
    return len(get_entity_configs(device_type)) > 0


def get_required_parameters() -> tuple[str, ...]:
    """Return all required parameters for custom entities."""
    required_parameters: list[str] = []
    for channel in entity_definition[ED_DEFAULT_ENTITIES]:
        required_parameters.extend(entity_definition[ED_DEFAULT_ENTITIES][channel])
    for device in entity_definition[ED_DEVICE_DEFINITIONS]:
        device_def = entity_definition[ED_DEVICE_DEFINITIONS][device][ED_DEVICE_GROUP]
        required_parameters.extend(list(device_def.get(ED_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED_VISIBLE_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED_REPEATABLE_FIELDS, {}).values()))
        for additional_entities in list(
            entity_definition[ED_DEVICE_DEFINITIONS][device]
            .get(ED_ADDITIONAL_ENTITIES, {})
            .values()
        ):
            required_parameters.extend(additional_entities)

    for platform_spec in ALL_DEVICES:
        for custom_configs in platform_spec.values():
            if isinstance(custom_configs, CustomConfig):
                if extended := custom_configs.extended:
                    required_parameters.extend(extended.required_parameters)
            else:
                for custom_config in custom_configs:
                    if extended := custom_config.extended:
                        required_parameters.extend(extended.required_parameters)

    return tuple(sorted(set(required_parameters)))
