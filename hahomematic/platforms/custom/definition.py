"""The module contains device descriptions for custom entities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any, Final, cast

import voluptuous as vol

from hahomematic import support as hms
from hahomematic.const import Parameter
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import entity as hmce
from hahomematic.platforms.custom.const import ED, DeviceProfile, Field
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.support import generate_unique_id

_LOGGER: Final = logging.getLogger(__name__)

DEFAULT_INCLUDE_DEFAULT_ENTITIES: Final = True

ALL_DEVICES: list[Mapping[str, CustomConfig | tuple[CustomConfig, ...]]] = []
ALL_BLACKLISTED_DEVICES: list[tuple[str, ...]] = []

SCHEMA_ED_ADDITIONAL_ENTITIES = vol.Schema(
    {vol.Required(vol.Any(int, tuple[int, ...])): vol.Schema((vol.Optional(Parameter),))}
)

SCHEMA_ED_FIELD_DETAILS = vol.Schema({vol.Required(Field): Parameter})

SCHEMA_ED_FIELD = vol.Schema({vol.Required(int): SCHEMA_ED_FIELD_DETAILS})

SCHEMA_ED_DEVICE_GROUP = vol.Schema(
    {
        vol.Required(ED.PRIMARY_CHANNEL.value): int,
        vol.Optional(ED.SECONDARY_CHANNELS.value): (int,),
        vol.Optional(ED.REPEATABLE_FIELDS.value): SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED.VISIBLE_REPEATABLE_FIELDS.value): SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED.FIELDS.value): SCHEMA_ED_FIELD,
        vol.Optional(ED.VISIBLE_FIELDS.value): SCHEMA_ED_FIELD,
    }
)

SCHEMA_ED_DEVICE_GROUPS = vol.Schema(
    {
        vol.Required(ED.DEVICE_GROUP.value): SCHEMA_ED_DEVICE_GROUP,
        vol.Optional(ED.ADDITIONAL_ENTITIES.value): SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Optional(
            ED.INCLUDE_DEFAULT_ENTITIES.value, default=DEFAULT_INCLUDE_DEFAULT_ENTITIES
        ): bool,
    }
)

SCHEMA_DEVICE_DESCRIPTION = vol.Schema(
    {
        vol.Required(ED.DEFAULT_ENTITIES.value): SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Required(ED.DEVICE_DEFINITIONS.value): vol.Schema(
            {
                vol.Required(DeviceProfile): SCHEMA_ED_DEVICE_GROUPS,
            }
        ),
    }
)

ENTITY_DEFINITION: Mapping[ED, Mapping[int | DeviceProfile, Any]] = {
    ED.DEFAULT_ENTITIES: {
        0: (
            Parameter.DUTY_CYCLE,
            Parameter.DUTYCYCLE,
            Parameter.LOW_BAT,
            Parameter.LOWBAT,
            Parameter.OPERATING_VOLTAGE,
            Parameter.RSSI_DEVICE,
            Parameter.RSSI_PEER,
            Parameter.SABOTAGE,
        ),
        2: (Parameter.BATTERY_STATE,),
        4: (Parameter.BATTERY_STATE,),
    },
    ED.DEVICE_DEFINITIONS: {
        DeviceProfile.IP_COVER: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.SECONDARY_CHANNELS: (2, 3),
                ED.REPEATABLE_FIELDS: {
                    Field.COMBINED_PARAMETER: Parameter.COMBINED_PARAMETER,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.LEVEL_2: Parameter.LEVEL_2,
                    Field.STOP: Parameter.STOP,
                },
                ED.FIELDS: {
                    0: {
                        Field.DIRECTION: Parameter.ACTIVITY_STATE,
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                        Field.CHANNEL_LEVEL_2: Parameter.LEVEL_2,
                        Field.CHANNEL_OPERATION_MODE: Parameter.CHANNEL_OPERATION_MODE,
                    },
                },
            },
        },
        DeviceProfile.IP_DIMMER: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.SECONDARY_CHANNELS: (2, 3),
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                ED.VISIBLE_FIELDS: {
                    0: {
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_GARAGE: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.DOOR_COMMAND: Parameter.DOOR_COMMAND,
                    Field.SECTION: Parameter.SECTION,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.DOOR_STATE: Parameter.DOOR_STATE,
                },
            },
            ED.ADDITIONAL_ENTITIES: {
                1: (Parameter.STATE,),
            },
        },
        DeviceProfile.IP_HDM: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.FIELDS: {
                    1: {
                        Field.DIRECTION: Parameter.ACTIVITY_STATE,
                        Field.LEVEL: Parameter.LEVEL,
                        Field.LEVEL_2: Parameter.LEVEL_2,
                        Field.STOP: Parameter.STOP,
                    },
                },
            },
        },
        DeviceProfile.IP_FIXED_COLOR_LIGHT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.SECONDARY_CHANNELS: (2, 3),
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
                ED.VISIBLE_FIELDS: {
                    0: {
                        Field.CHANNEL_COLOR: Parameter.COLOR,
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                    Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
            },
        },
        DeviceProfile.IP_RGBW_LIGHT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.SECONDARY_CHANNELS: (2, 3, 4),
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR_TEMPERATURE: Parameter.COLOR_TEMPERATURE,
                    Field.DIRECTION: Parameter.ACTIVITY_STATE,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.EFFECT: Parameter.EFFECT,
                    Field.HUE: Parameter.HUE,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.RAMP_TIME_TO_OFF_UNIT: Parameter.RAMP_TIME_TO_OFF_UNIT,
                    Field.RAMP_TIME_TO_OFF_VALUE: Parameter.RAMP_TIME_TO_OFF_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                    Field.SATURATION: Parameter.SATURATION,
                },
                ED.FIELDS: {
                    0: {
                        Field.DEVICE_OPERATION_MODE: Parameter.DEVICE_OPERATION_MODE,
                    },
                },
            },
        },
        DeviceProfile.IP_SWITCH: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.SECONDARY_CHANNELS: (2, 3),
                ED.REPEATABLE_FIELDS: {
                    Field.STATE: Parameter.STATE,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                },
                ED.VISIBLE_FIELDS: {
                    0: {
                        Field.CHANNEL_STATE: Parameter.STATE,
                    },
                },
            },
            ED.ADDITIONAL_ENTITIES: {
                4: (
                    Parameter.CURRENT,
                    Parameter.ENERGY_COUNTER,
                    Parameter.FREQUENCY,
                    Parameter.POWER,
                    Parameter.ACTUAL_TEMPERATURE,
                    Parameter.VOLTAGE,
                ),
            },
        },
        DeviceProfile.IP_LOCK: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.ACTIVITY_STATE,
                    Field.LOCK_STATE: Parameter.LOCK_STATE,
                    Field.LOCK_TARGET_LEVEL: Parameter.LOCK_TARGET_LEVEL,
                },
                ED.FIELDS: {
                    0: {
                        Field.ERROR: Parameter.ERROR_JAMMED,
                    },
                },
            },
        },
        DeviceProfile.IP_SIREN: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 3,
                ED.REPEATABLE_FIELDS: {
                    Field.ACOUSTIC_ALARM_ACTIVE: Parameter.ACOUSTIC_ALARM_ACTIVE,
                    Field.OPTICAL_ALARM_ACTIVE: Parameter.OPTICAL_ALARM_ACTIVE,
                    Field.ACOUSTIC_ALARM_SELECTION: Parameter.ACOUSTIC_ALARM_SELECTION,
                    Field.OPTICAL_ALARM_SELECTION: Parameter.OPTICAL_ALARM_SELECTION,
                    Field.DURATION: Parameter.DURATION_VALUE,
                    Field.DURATION_UNIT: Parameter.DURATION_UNIT,
                },
            },
        },
        DeviceProfile.IP_SIREN_SMOKE: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 1,
                ED.REPEATABLE_FIELDS: {
                    Field.SMOKE_DETECTOR_COMMAND: Parameter.SMOKE_DETECTOR_COMMAND,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.SMOKE_DETECTOR_ALARM_STATUS: Parameter.SMOKE_DETECTOR_ALARM_STATUS,
                },
            },
        },
        DeviceProfile.IP_THERMOSTAT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
                    Field.PARTY_MODE: Parameter.PARTY_MODE,
                    Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
                    Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                ED.VISIBLE_FIELDS: {
                    0: {
                        Field.LEVEL: Parameter.LEVEL,
                        Field.CONCENTRATION: Parameter.CONCENTRATION,
                    },
                    8: {
                        Field.STATE: Parameter.STATE,
                    },
                },
            },
        },
        DeviceProfile.IP_THERMOSTAT_GROUP: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
                    Field.PARTY_MODE: Parameter.PARTY_MODE,
                    Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
                    Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                ED.FIELDS: {
                    0: {
                        Field.LEVEL: Parameter.LEVEL,
                    },
                    3: {
                        Field.STATE: Parameter.STATE,
                    },
                },
            },
            ED.INCLUDE_DEFAULT_ENTITIES: False,
        },
        DeviceProfile.RF_COVER: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.DIRECTION,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.LEVEL_2: Parameter.LEVEL_SLATS,
                    Field.LEVEL_COMBINED: Parameter.LEVEL_COMBINED,
                    Field.STOP: Parameter.STOP,
                },
            },
        },
        DeviceProfile.RF_DIMMER: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                ED.FIELDS: {
                    1: {
                        Field.COLOR: Parameter.COLOR,
                    },
                    2: {
                        Field.PROGRAM: Parameter.PROGRAM,
                    },
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR_FIXED: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR_TEMP: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                ED.FIELDS: {
                    1: {
                        Field.COLOR_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.SECONDARY_CHANNELS: (1, 2),
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_LOCK: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.DIRECTION,
                    Field.OPEN: Parameter.OPEN,
                    Field.STATE: Parameter.STATE,
                    Field.ERROR: Parameter.ERROR,
                },
            },
        },
        DeviceProfile.RF_SWITCH: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.STATE: Parameter.STATE,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                },
            },
            ED.ADDITIONAL_ENTITIES: {
                1: (
                    Parameter.CURRENT,
                    Parameter.ENERGY_COUNTER,
                    Parameter.FREQUENCY,
                    Parameter.POWER,
                    Parameter.VOLTAGE,
                ),
            },
        },
        DeviceProfile.RF_THERMOSTAT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                ED.VISIBLE_FIELDS: {
                    0: {
                        Field.VALVE_STATE: Parameter.VALVE_STATE,
                    },
                },
            },
        },
        DeviceProfile.RF_THERMOSTAT_GROUP: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.ACTUAL_HUMIDITY,
                    Field.TEMPERATURE: Parameter.ACTUAL_TEMPERATURE,
                },
                ED.FIELDS: {
                    0: {
                        Field.VALVE_STATE: Parameter.VALVE_STATE,
                    },
                },
            },
            ED.INCLUDE_DEFAULT_ENTITIES: False,
        },
        DeviceProfile.SIMPLE_RF_THERMOSTAT: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: 0,
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HUMIDITY: Parameter.HUMIDITY,
                    Field.TEMPERATURE: Parameter.TEMPERATURE,
                },
                ED.FIELDS: {
                    1: {
                        Field.SETPOINT: Parameter.SETPOINT,
                    },
                },
            },
        },
    },
}


def validate_entity_definition() -> Any:
    """Validate the entity_definition."""
    try:
        return SCHEMA_DEVICE_DESCRIPTION(ENTITY_DEFINITION)
    except vol.Invalid as err:  # pragma: no cover
        _LOGGER.error("The entity definition could not be validated. %s, %s", err.path, err.msg)
        return None


def make_custom_entity(
    device: hmd.HmDevice,
    entity_class: type,
    device_profile: DeviceProfile,
    group_base_channels: tuple[int, ...],
    extended: ExtendedConfig | None = None,
) -> tuple[hmce.CustomEntity, ...]:
    """
    Create custom_entities.

    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities: list[hmce.CustomEntity] = []

    entity_def = _get_device_entities(device_profile, group_base_channels[0])

    for base_channel_no in group_base_channels:
        device_def = _get_device_group(device_profile, base_channel_no)
        channels = [device_def[ED.PRIMARY_CHANNEL]]
        if secondary_channels := device_def.get(ED.SECONDARY_CHANNELS):
            channels.extend(secondary_channels)
        for channel_no in set(channels):
            entities.extend(
                _create_entities(
                    device=device,
                    custom_entity_class=entity_class,
                    device_profile=device_profile,
                    device_def=device_def,
                    entity_def=entity_def,
                    channel_no=channel_no,
                    base_channel_no=base_channel_no,
                    extended=extended,
                )
            )

    return tuple(entities)


def _create_entities(
    device: hmd.HmDevice,
    custom_entity_class: type,
    device_profile: DeviceProfile,
    device_def: Mapping[ED, Any],
    entity_def: Mapping[int, tuple[Parameter, ...]],
    channel_no: int | None = None,
    base_channel_no: int | None = None,
    extended: ExtendedConfig | None = None,
) -> tuple[hmce.CustomEntity, ...]:
    """Create custom entities."""
    entities: list[hmce.CustomEntity] = []
    channel_address = hms.get_channel_address(
        device_address=device.device_address, channel_no=channel_no
    )
    unique_id = generate_unique_id(central=device.central, address=channel_address)
    if channel_address not in device.channels:
        return tuple(entities)
    entity = custom_entity_class(
        device=device,
        unique_id=unique_id,
        device_profile=device_profile,
        device_def=device_def,
        entity_def=entity_def,
        channel_no=channel_no,
        base_channel_no=base_channel_no,
        extended=extended,
    )
    if entity.has_data_entities:
        device.add_entity(entity)
        entities.append(entity)
    return tuple(entities)


def get_default_entities() -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Return the default entities."""
    return ENTITY_DEFINITION[ED.DEFAULT_ENTITIES]  # type: ignore[return-value]


def get_include_default_entities(device_profile: DeviceProfile) -> bool:
    """Return if default entities should be included."""
    device = _get_device_definition(device_profile)
    return device.get(ED.INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES)


def _get_device_definition(device_profile: DeviceProfile) -> Mapping[ED, Any]:
    """Return device from entity definitions."""
    return cast(Mapping[ED, Any], ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device_profile])


def _get_device_group(device_profile: DeviceProfile, base_channel_no: int) -> Mapping[ED, Any]:
    """Return the device group."""
    device = _get_device_definition(device_profile)
    group = cast(dict[ED, Any], device[ED.DEVICE_GROUP])
    if group and base_channel_no == 0:
        return group

    # Create a deep copy of the group due to channel rebase
    group = deepcopy(group)
    # Add base_channel_no to the primary_channel to get the real primary_channel number
    primary_channel = group[ED.PRIMARY_CHANNEL]
    group[ED.PRIMARY_CHANNEL] = primary_channel + base_channel_no

    # Add base_channel_no to the secondary_channels
    # to get the real secondary_channel numbers
    if secondary_channel := group.get(ED.SECONDARY_CHANNELS):
        group[ED.SECONDARY_CHANNELS] = [x + base_channel_no for x in secondary_channel]

    group[ED.VISIBLE_FIELDS] = _rebase_entity_dict(
        entity_dict=ED.VISIBLE_FIELDS, group=group, base_channel_no=base_channel_no
    )
    group[ED.FIELDS] = _rebase_entity_dict(
        entity_dict=ED.FIELDS, group=group, base_channel_no=base_channel_no
    )
    return group


def _rebase_entity_dict(
    entity_dict: ED, group: Mapping[ED, Any], base_channel_no: int
) -> Mapping[int, Any]:
    """Rebase entity_dict with base_channel_no."""
    new_fields = {}
    if fields := group.get(entity_dict):
        for channel_no, field in fields.items():
            new_fields[channel_no + base_channel_no] = field
    return new_fields


def _get_device_entities(
    device_profile: DeviceProfile, base_channel_no: int
) -> Mapping[int, tuple[Parameter, ...]]:
    """Return the device entities."""
    additional_entities = (
        ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS]
        .get(device_profile, {})
        .get(ED.ADDITIONAL_ENTITIES, {})
    )
    new_entities: dict[int, tuple[Parameter, ...]] = {}
    if additional_entities:
        for channel_no, field in additional_entities.items():
            new_entities[channel_no + base_channel_no] = field
    return new_entities


def get_entity_configs(
    device_type: str,
) -> tuple[CustomConfig | tuple[CustomConfig, ...], ...]:
    """Return the entity configs to create custom entities."""
    device_type = device_type.lower().replace("hb-", "hm-")
    funcs = []
    for platform_blacklisted_devices in ALL_BLACKLISTED_DEVICES:
        if hms.element_matches_key(
            search_elements=platform_blacklisted_devices,
            compare_with=device_type,
        ):
            return ()

    for platform_devices in ALL_DEVICES:
        if func := _get_entity_config_by_platform(
            platform_devices=platform_devices,
            device_type=device_type,
        ):
            funcs.append(func)
    return tuple(funcs)


def _get_entity_config_by_platform(
    platform_devices: Mapping[str, CustomConfig | tuple[CustomConfig, ...]],
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


def get_required_parameters() -> tuple[Parameter, ...]:
    """Return all required parameters for custom entities."""
    required_parameters: list[Parameter] = []
    for channel in ENTITY_DEFINITION[ED.DEFAULT_ENTITIES]:
        required_parameters.extend(ENTITY_DEFINITION[ED.DEFAULT_ENTITIES][channel])
    for device in ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS]:
        device_def = ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device][ED.DEVICE_GROUP]
        required_parameters.extend(list(device_def.get(ED.REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED.VISIBLE_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED.REPEATABLE_FIELDS, {}).values()))
        for additional_entities in list(
            ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device]
            .get(ED.ADDITIONAL_ENTITIES, {})
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
