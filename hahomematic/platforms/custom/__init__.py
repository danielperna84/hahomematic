"""Module for HaHomematic custom platforms."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom.climate import (
    HM_PRESET_MODE_PREFIX,
    PROFILE_DICT,
    SIMPLE_PROFILE_DICT,
    SIMPLE_WEEKDAY_LIST,
    WEEKDAY_DICT,
    BaseClimateEntity,
    CeIpThermostat,
    CeRfThermostat,
    CeSimpleRfThermostat,
    HmHvacAction,
    HmHvacMode,
    HmPresetMode,
)
from hahomematic.platforms.custom.cover import CeBlind, CeCover, CeGarage, CeIpBlind, CeWindowDrive
from hahomematic.platforms.custom.definition import (
    entity_definition_exists,
    get_custom_configs,
    get_required_parameters,
    validate_entity_definition,
)
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.light import (
    CeColorDimmer,
    CeColorDimmerEffect,
    CeColorTempDimmer,
    CeDimmer,
    CeIpDrgDaliLight,
    CeIpFixedColorLight,
    CeIpRGBWLight,
    LightOffArgs,
    LightOnArgs,
)
from hahomematic.platforms.custom.lock import BaseLock, CeButtonLock, CeIpLock, CeRfLock, LockState
from hahomematic.platforms.custom.siren import BaseSiren, CeIpSiren, CeIpSirenSmoke, SirenOnArgs
from hahomematic.platforms.custom.switch import CeSwitch

__all__ = [
    "BaseClimateEntity",
    "BaseLock",
    "BaseSiren",
    "CeBlind",
    "CeButtonLock",
    "CeColorDimmer",
    "CeColorDimmerEffect",
    "CeColorTempDimmer",
    "CeCover",
    "CeDimmer",
    "CeGarage",
    "CeIpBlind",
    "CeIpDrgDaliLight",
    "CeIpFixedColorLight",
    "CeIpLock",
    "CeIpRGBWLight",
    "CeIpSiren",
    "CeIpSirenSmoke",
    "CeIpThermostat",
    "CeRfLock",
    "CeRfThermostat",
    "CeSimpleRfThermostat",
    "CeSwitch",
    "CeWindowDrive",
    "CustomEntity",
    "HM_PRESET_MODE_PREFIX",
    "HmHvacAction",
    "HmHvacMode",
    "HmPresetMode",
    "LightOffArgs",
    "LightOnArgs",
    "LockState",
    "SirenOnArgs",
    "WEEKDAY_DICT",
    "PROFILE_DICT",
    "SIMPLE_PROFILE_DICT",
    "SIMPLE_WEEKDAY_LIST",
    "create_custom_entities",
    "get_required_parameters",
    "validate_entity_definition",
]

_LOGGER: Final = logging.getLogger(__name__)


def create_custom_entities(device: hmd.HmDevice) -> None:
    """Decides which default platform should be used, and creates the required entities."""

    if device.ignore_for_custom_entity:
        _LOGGER.debug(
            "CREATE_ENTITIES: Ignoring for custom entity: %s, %s, %s due to ignored",
            device.interface_id,
            device,
            device.model,
        )
        return
    if entity_definition_exists(device.model):
        _LOGGER.debug(
            "CREATE_ENTITIES: Handling custom entity integration: %s, %s, %s",
            device.interface_id,
            device,
            device.model,
        )

        # Call the custom creation function.
        for custom_config in get_custom_configs(model=device.model):
            for channel in device.channels.values():
                custom_config.make_ce_func(channel, custom_config)
