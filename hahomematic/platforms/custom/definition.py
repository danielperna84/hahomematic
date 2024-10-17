"""The module contains device descriptions for custom entities."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import logging
from typing import Any, Final, cast

import voluptuous as vol

from hahomematic import support as hms, validator as val
from hahomematic.const import HmPlatform, Parameter
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom.const import ED, DeviceProfile, Field
from hahomematic.platforms.custom.support import CustomConfig
from hahomematic.platforms.support import generate_unique_id
from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)

DEFAULT_INCLUDE_DEFAULT_ENTITIES: Final = True

ALL_DEVICES: dict[HmPlatform, Mapping[str, CustomConfig | tuple[CustomConfig, ...]]] = {}
ALL_BLACKLISTED_DEVICES: list[tuple[str, ...]] = []

_SCHEMA_ED_ADDITIONAL_ENTITIES = vol.Schema(
    {
        vol.Required(vol.Any(val.positive_int, tuple[int, ...])): vol.Schema(
            (vol.Optional(Parameter),)
        )
    }
)

_SCHEMA_ED_FIELD_DETAILS = vol.Schema({vol.Required(Field): Parameter})

_SCHEMA_ED_FIELD = vol.Schema({vol.Required(int): _SCHEMA_ED_FIELD_DETAILS})

_SCHEMA_ED_DEVICE_GROUP = vol.Schema(
    {
        vol.Required(ED.PRIMARY_CHANNEL.value, default=0): vol.Any(val.positive_int, None),
        vol.Required(ED.ALLOW_UNDEFINED_GENERIC_ENTITIES.value, default=False): bool,
        vol.Optional(ED.SECONDARY_CHANNELS.value): (val.positive_int,),
        vol.Optional(ED.REPEATABLE_FIELDS.value): _SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED.VISIBLE_REPEATABLE_FIELDS.value): _SCHEMA_ED_FIELD_DETAILS,
        vol.Optional(ED.FIELDS.value): _SCHEMA_ED_FIELD,
        vol.Optional(ED.VISIBLE_FIELDS.value): _SCHEMA_ED_FIELD,
    }
)

_SCHEMA_ED_DEVICE_GROUPS = vol.Schema(
    {
        vol.Required(ED.DEVICE_GROUP.value): _SCHEMA_ED_DEVICE_GROUP,
        vol.Optional(ED.ADDITIONAL_ENTITIES.value): _SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Optional(
            ED.INCLUDE_DEFAULT_ENTITIES.value, default=DEFAULT_INCLUDE_DEFAULT_ENTITIES
        ): bool,
    }
)

_SCHEMA_DEVICE_DESCRIPTION = vol.Schema(
    {
        vol.Required(ED.DEFAULT_ENTITIES.value): _SCHEMA_ED_ADDITIONAL_ENTITIES,
        vol.Required(ED.DEVICE_DEFINITIONS.value): vol.Schema(
            {
                vol.Required(DeviceProfile): _SCHEMA_ED_DEVICE_GROUPS,
            }
        ),
    }
)

_ENTITY_DEFINITION: Mapping[ED, Mapping[int | DeviceProfile, Any]] = {
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
        DeviceProfile.IP_BUTTON_LOCK: {
            ED.DEVICE_GROUP: {
                ED.ALLOW_UNDEFINED_GENERIC_ENTITIES: True,
                ED.REPEATABLE_FIELDS: {
                    Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
                },
            },
        },
        DeviceProfile.IP_COVER: {
            ED.DEVICE_GROUP: {
                ED.SECONDARY_CHANNELS: (1, 2),
                ED.REPEATABLE_FIELDS: {
                    Field.COMBINED_PARAMETER: Parameter.COMBINED_PARAMETER,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.LEVEL_2: Parameter.LEVEL_2,
                    Field.STOP: Parameter.STOP,
                },
                ED.FIELDS: {
                    -1: {
                        Field.DIRECTION: Parameter.ACTIVITY_STATE,
                        Field.OPERATION_MODE: Parameter.CHANNEL_OPERATION_MODE,
                    },
                },
                ED.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                        Field.CHANNEL_LEVEL_2: Parameter.LEVEL_2,
                    },
                },
            },
        },
        DeviceProfile.IP_DIMMER: {
            ED.DEVICE_GROUP: {
                ED.SECONDARY_CHANNELS: (1, 2),
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
                ED.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_GARAGE: {
            ED.DEVICE_GROUP: {
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
                ED.FIELDS: {
                    0: {
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
                ED.SECONDARY_CHANNELS: (1, 2),
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
                ED.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_COLOR: Parameter.COLOR,
                        Field.CHANNEL_LEVEL: Parameter.LEVEL,
                    },
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED: {
            ED.DEVICE_GROUP: {
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR: Parameter.COLOR,
                    Field.COLOR_BEHAVIOUR: Parameter.COLOR_BEHAVIOUR,
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_UNIT: Parameter.DURATION_UNIT,
                    Field.ON_TIME_VALUE: Parameter.DURATION_VALUE,
                    Field.RAMP_TIME_UNIT: Parameter.RAMP_TIME_UNIT,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME_VALUE,
                },
            },
        },
        DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT: {
            ED.DEVICE_GROUP: {
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
                ED.SECONDARY_CHANNELS: (1, 2, 3),
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
                    -1: {
                        Field.DEVICE_OPERATION_MODE: Parameter.DEVICE_OPERATION_MODE,
                    },
                },
            },
        },
        DeviceProfile.IP_DRG_DALI: {
            ED.DEVICE_GROUP: {
                ED.REPEATABLE_FIELDS: {
                    Field.COLOR_TEMPERATURE: Parameter.COLOR_TEMPERATURE,
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
            },
        },
        DeviceProfile.IP_SWITCH: {
            ED.DEVICE_GROUP: {
                ED.SECONDARY_CHANNELS: (1, 2),
                ED.REPEATABLE_FIELDS: {
                    Field.STATE: Parameter.STATE,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                },
                ED.VISIBLE_FIELDS: {
                    -1: {
                        Field.CHANNEL_STATE: Parameter.STATE,
                    },
                },
            },
            ED.ADDITIONAL_ENTITIES: {
                3: (
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
                ED.REPEATABLE_FIELDS: {
                    Field.DIRECTION: Parameter.ACTIVITY_STATE,
                    Field.LOCK_STATE: Parameter.LOCK_STATE,
                    Field.LOCK_TARGET_LEVEL: Parameter.LOCK_TARGET_LEVEL,
                },
                ED.FIELDS: {
                    -1: {
                        Field.ERROR: Parameter.ERROR_JAMMED,
                    },
                },
            },
        },
        DeviceProfile.IP_SIREN: {
            ED.DEVICE_GROUP: {
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
                ED.REPEATABLE_FIELDS: {
                    Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.OPTIMUM_START_STOP: Parameter.OPTIMUM_START_STOP,
                    Field.PARTY_MODE: Parameter.PARTY_MODE,
                    Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
                    Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
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
                ED.REPEATABLE_FIELDS: {
                    Field.ACTIVE_PROFILE: Parameter.ACTIVE_PROFILE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.OPTIMUM_START_STOP: Parameter.OPTIMUM_START_STOP,
                    Field.PARTY_MODE: Parameter.PARTY_MODE,
                    Field.SETPOINT: Parameter.SET_POINT_TEMPERATURE,
                    Field.SET_POINT_MODE: Parameter.SET_POINT_MODE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
                },
                ED.VISIBLE_REPEATABLE_FIELDS: {
                    Field.HEATING_COOLING: Parameter.HEATING_COOLING,
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
        DeviceProfile.RF_BUTTON_LOCK: {
            ED.DEVICE_GROUP: {
                ED.PRIMARY_CHANNEL: None,
                ED.ALLOW_UNDEFINED_GENERIC_ENTITIES: True,
                ED.REPEATABLE_FIELDS: {
                    Field.BUTTON_LOCK: Parameter.GLOBAL_BUTTON_LOCK,
                },
            },
        },
        DeviceProfile.RF_COVER: {
            ED.DEVICE_GROUP: {
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
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR: {
            ED.DEVICE_GROUP: {
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
                ED.REPEATABLE_FIELDS: {
                    Field.LEVEL: Parameter.LEVEL,
                    Field.ON_TIME_VALUE: Parameter.ON_TIME,
                    Field.RAMP_TIME_VALUE: Parameter.RAMP_TIME,
                },
            },
        },
        DeviceProfile.RF_DIMMER_COLOR_TEMP: {
            ED.DEVICE_GROUP: {
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
                ED.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
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
                ED.REPEATABLE_FIELDS: {
                    Field.AUTO_MODE: Parameter.AUTO_MODE,
                    Field.BOOST_MODE: Parameter.BOOST_MODE,
                    Field.COMFORT_MODE: Parameter.COMFORT_MODE,
                    Field.CONTROL_MODE: Parameter.CONTROL_MODE,
                    Field.LOWERING_MODE: Parameter.LOWERING_MODE,
                    Field.MANU_MODE: Parameter.MANU_MODE,
                    Field.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE: Parameter.MIN_MAX_VALUE_NOT_RELEVANT_FOR_MANU_MODE,
                    Field.SETPOINT: Parameter.SET_TEMPERATURE,
                    Field.TEMPERATURE_MAXIMUM: Parameter.TEMPERATURE_MAXIMUM,
                    Field.TEMPERATURE_MINIMUM: Parameter.TEMPERATURE_MINIMUM,
                    Field.TEMPERATURE_OFFSET: Parameter.TEMPERATURE_OFFSET,
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

VALID_ENTITY_DEFINITION = _SCHEMA_DEVICE_DESCRIPTION(_ENTITY_DEFINITION)


def validate_entity_definition() -> Any:
    """Validate the entity_definition."""
    try:
        return _SCHEMA_DEVICE_DESCRIPTION(_ENTITY_DEFINITION)
    except vol.Invalid as err:  # pragma: no cover
        _LOGGER.error("The entity definition could not be validated. %s, %s", err.path, err.msg)
        return None


def make_custom_entity(
    channel: hmd.HmChannel,
    entity_class: type,
    device_profile: DeviceProfile,
    custom_config: CustomConfig,
) -> None:
    """
    Create custom_entities.

    We use a helper-function to avoid raising exceptions during object-init.
    """
    add_sub_device_channels_to_device(
        device=channel.device, device_profile=device_profile, custom_config=custom_config
    )
    base_channel_no = get_sub_device_base_channel(device=channel.device, channel_no=channel.no)
    channels = _relevant_channels(device_profile=device_profile, custom_config=custom_config)
    if channel.no in set(channels):
        _create_entity(
            channel=channel,
            custom_entity_class=entity_class,
            device_profile=device_profile,
            device_def=_get_device_group(device_profile, base_channel_no),
            entity_def=_get_device_entities(device_profile, base_channel_no),
            base_channel_no=base_channel_no,
            custom_config=_rebase_pri_channels(
                device_profile=device_profile, custom_config=custom_config
            ),
        )


def _create_entity(
    channel: hmd.HmChannel,
    custom_entity_class: type,
    device_profile: DeviceProfile,
    device_def: Mapping[ED, Any],
    entity_def: Mapping[int, tuple[Parameter, ...]],
    base_channel_no: int | None,
    custom_config: CustomConfig,
) -> None:
    """Create custom entities."""
    unique_id = generate_unique_id(central=channel.central, address=channel.address)

    try:
        if (
            entity := custom_entity_class(
                channel=channel,
                unique_id=unique_id,
                device_profile=device_profile,
                device_def=device_def,
                entity_def=entity_def,
                base_channel_no=base_channel_no,
                custom_config=custom_config,
            )
        ) and entity.has_data_entities:
            channel.add_entity(entity)
    except Exception as ex:
        raise HaHomematicException(
            f"_CREATE_ENTITY: unable to create entity: {reduce_args(args=ex.args)}"
        ) from ex


def _rebase_pri_channels(
    device_profile: DeviceProfile, custom_config: CustomConfig
) -> CustomConfig:
    """Re base primary channel of custom config."""
    device_def = _get_device_group(device_profile, 0)
    if (pri_def := device_def[ED.PRIMARY_CHANNEL]) is None:
        return custom_config
    pri_channels = [cu + pri_def for cu in custom_config.channels]
    return CustomConfig(
        make_ce_func=custom_config.make_ce_func,
        channels=tuple(pri_channels),
        extended=custom_config.extended,
    )


def _relevant_channels(
    device_profile: DeviceProfile, custom_config: CustomConfig
) -> tuple[int | None, ...]:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile, 0)
    def_channels = [device_def[ED.PRIMARY_CHANNEL]]
    if sec_channels := device_def.get(ED.SECONDARY_CHANNELS):
        def_channels.extend(sec_channels)

    channels: set[int | None] = set()
    for def_ch in def_channels:
        for conf_ch in custom_config.channels:
            if def_ch is not None and conf_ch is not None:
                channels.add(def_ch + conf_ch)
            else:
                channels.add(None)
    return tuple(channels)


def add_sub_device_channels_to_device(
    device: hmd.HmDevice, device_profile: DeviceProfile, custom_config: CustomConfig
) -> None:
    """Return the relevant channels."""
    device_def = _get_device_group(device_profile, 0)
    pri_channel = device_def[ED.PRIMARY_CHANNEL]
    sec_channels = device_def.get(ED.SECONDARY_CHANNELS)
    if pri_channel is None:
        return
    for conf_channel in custom_config.channels:
        if conf_channel is None:
            continue
        rebased_pri_channel = conf_channel + pri_channel
        device.add_sub_device_channel(
            channel_no=rebased_pri_channel, base_channel_no=rebased_pri_channel
        )
        if sec_channels:
            for sec_channel in sec_channels:
                device.add_sub_device_channel(
                    channel_no=conf_channel + sec_channel, base_channel_no=rebased_pri_channel
                )


def get_sub_device_base_channel(device: hmd.HmDevice, channel_no: int | None) -> int | None:
    """Get base channel of sub_device."""
    return device.get_sub_device_base_channel(channel_no=channel_no)


def get_default_entities() -> Mapping[int | tuple[int, ...], tuple[Parameter, ...]]:
    """Return the default entities."""
    return VALID_ENTITY_DEFINITION[ED.DEFAULT_ENTITIES]  # type: ignore[no-any-return]


def get_include_default_entities(device_profile: DeviceProfile) -> bool:
    """Return if default entities should be included."""
    device = _get_device_definition(device_profile)
    return device.get(ED.INCLUDE_DEFAULT_ENTITIES, DEFAULT_INCLUDE_DEFAULT_ENTITIES)


def _get_device_definition(device_profile: DeviceProfile) -> Mapping[ED, Any]:
    """Return device from entity definitions."""
    return cast(Mapping[ED, Any], VALID_ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device_profile])


def _get_device_group(
    device_profile: DeviceProfile, base_channel_no: int | None
) -> Mapping[ED, Any]:
    """Return the device group."""
    device = _get_device_definition(device_profile)
    group = cast(dict[ED, Any], device[ED.DEVICE_GROUP])
    # Create a deep copy of the group due to channel rebase
    group = deepcopy(group)
    if not base_channel_no:
        return group
    # Add base_channel_no to the primary_channel to get the real primary_channel number
    if (primary_channel := group[ED.PRIMARY_CHANNEL]) is not None:
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
    device_profile: DeviceProfile, base_channel_no: int | None
) -> Mapping[int, tuple[Parameter, ...]]:
    """Return the device entities."""
    additional_entities = (
        VALID_ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS]
        .get(device_profile, {})
        .get(ED.ADDITIONAL_ENTITIES, {})
    )
    if not base_channel_no:
        return additional_entities  # type: ignore[no-any-return]
    new_entities: dict[int, tuple[Parameter, ...]] = {}
    if additional_entities:
        for channel_no, field in additional_entities.items():
            new_entities[channel_no + base_channel_no] = field
    return new_entities


def get_custom_configs(
    model: str,
    platform: HmPlatform | None = None,
) -> tuple[CustomConfig, ...]:
    """Return the entity configs to create custom entities."""
    model = model.lower().replace("hb-", "hm-")
    custom_configs: list[CustomConfig] = []
    for platform_blacklisted_devices in ALL_BLACKLISTED_DEVICES:
        if hms.element_matches_key(
            search_elements=platform_blacklisted_devices,
            compare_with=model,
        ):
            return ()

    for pf, platform_devices in ALL_DEVICES.items():
        if platform is not None and pf != platform:
            continue
        if func := _get_entity_config_by_platform(
            platform_devices=platform_devices,
            model=model,
        ):
            if isinstance(func, tuple):
                custom_configs.extend(func)  # noqa:PERF401
            else:
                custom_configs.append(func)
    return tuple(custom_configs)


def _get_entity_config_by_platform(
    platform_devices: Mapping[str, CustomConfig | tuple[CustomConfig, ...]],
    model: str,
) -> CustomConfig | tuple[CustomConfig, ...] | None:
    """Return the entity configs to create custom entities."""
    for d_type, custom_configs in platform_devices.items():
        if model.lower() == d_type.lower():
            return custom_configs

    for d_type, custom_configs in platform_devices.items():
        if model.lower().startswith(d_type.lower()):
            return custom_configs

    return None


def is_multi_channel_device(model: str, platform: HmPlatform) -> bool:
    """Return true, if device has multiple channels."""
    channels: list[int | None] = []
    for custom_config in get_custom_configs(model=model, platform=platform):
        channels.extend(custom_config.channels)
    return len(channels) > 1


def entity_definition_exists(model: str) -> bool:
    """Check if device desc exits."""
    return len(get_custom_configs(model)) > 0


def get_required_parameters() -> tuple[Parameter, ...]:
    """Return all required parameters for custom entities."""
    required_parameters: list[Parameter] = []
    for channel in VALID_ENTITY_DEFINITION[ED.DEFAULT_ENTITIES]:
        required_parameters.extend(VALID_ENTITY_DEFINITION[ED.DEFAULT_ENTITIES][channel])
    for device in VALID_ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS]:
        device_def = VALID_ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device][ED.DEVICE_GROUP]
        required_parameters.extend(list(device_def.get(ED.REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED.VISIBLE_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED.REPEATABLE_FIELDS, {}).values()))
        for additional_entities in list(
            VALID_ENTITY_DEFINITION[ED.DEVICE_DEFINITIONS][device]
            .get(ED.ADDITIONAL_ENTITIES, {})
            .values()
        ):
            required_parameters.extend(additional_entities)

    for platform_spec in ALL_DEVICES.values():
        for custom_configs in platform_spec.values():
            if isinstance(custom_configs, CustomConfig):
                if extended := custom_configs.extended:
                    required_parameters.extend(extended.required_parameters)
            else:
                for custom_config in custom_configs:
                    if extended := custom_config.extended:
                        required_parameters.extend(extended.required_parameters)

    return tuple(sorted(set(required_parameters)))
