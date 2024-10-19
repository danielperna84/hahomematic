"""Module for HaHomematic generic platforms."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from hahomematic import support as hms
from hahomematic.const import (
    CLICK_EVENTS,
    VIRTUAL_REMOTE_MODELS,
    Operations,
    Parameter,
    ParameterData,
    ParameterType,
    ParamsetKey,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.generic.button import HmButton
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.generic.number import BaseNumber, HmFloat, HmInteger
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch
from hahomematic.platforms.generic.text import HmText
from hahomematic.platforms.support import is_binary_sensor

__all__ = [
    "BaseNumber",
    "GenericEntity",
    "HmAction",
    "HmBinarySensor",
    "HmButton",
    "HmFloat",
    "HmInteger",
    "HmSelect",
    "HmSensor",
    "HmSwitch",
    "HmText",
    "create_entity_and_append_to_channel",
]

_LOGGER: Final = logging.getLogger(__name__)
_BUTTON_ACTIONS: Final[tuple[str, ...]] = ("RESET_MOTION", "RESET_PRESENCE")

# Entities that should be wrapped in a new entity on a new platform.
_SWITCH_ENTITY_TO_SENSOR: Final[Mapping[str | tuple[str, ...], Parameter]] = {
    ("HmIP-eTRV", "HmIP-HEATING"): Parameter.LEVEL,
}


def create_entity_and_append_to_channel(
    channel: hmd.HmChannel,
    paramset_key: ParamsetKey,
    parameter: str,
    parameter_data: ParameterData,
) -> None:
    """Decides which default platform should be used, and creates the required entities."""
    _LOGGER.debug(
        "CREATE_ENTITIES: Creating entity for %s, %s, %s",
        channel.address,
        parameter,
        channel.device.interface_id,
    )
    p_type = parameter_data["TYPE"]
    p_operations = parameter_data["OPERATIONS"]
    entity_t: type[GenericEntity] | None = None
    if p_operations & Operations.WRITE:
        if p_type == ParameterType.ACTION:
            if p_operations == Operations.WRITE:
                if parameter in _BUTTON_ACTIONS or channel.device.model in VIRTUAL_REMOTE_MODELS:
                    entity_t = HmButton
                else:
                    entity_t = HmAction
            elif parameter in CLICK_EVENTS:
                entity_t = HmButton
            else:
                entity_t = HmSwitch
        elif p_operations == Operations.WRITE:
            entity_t = HmAction
        elif p_type == ParameterType.BOOL:
            entity_t = HmSwitch
        elif p_type == ParameterType.ENUM:
            entity_t = HmSelect
        elif p_type == ParameterType.FLOAT:
            entity_t = HmFloat
        elif p_type == ParameterType.INTEGER:
            entity_t = HmInteger
        elif p_type == ParameterType.STRING:
            entity_t = HmText
    elif parameter not in CLICK_EVENTS:
        # Also check, if sensor could be a binary_sensor due to.
        if is_binary_sensor(parameter_data):
            parameter_data["TYPE"] = ParameterType.BOOL
            entity_t = HmBinarySensor
        else:
            entity_t = HmSensor

    if entity_t:
        try:
            entity = entity_t(
                channel=channel,
                paramset_key=paramset_key,
                parameter=parameter,
                parameter_data=parameter_data,
            )
        except Exception as ex:
            raise HaHomematicException(
                f"CREATE_ENTITY_AND_APPEND_TO_CHANNEL: Unable to create entity:{hms.reduce_args(args=ex.args)}"
            ) from ex
        _LOGGER.debug(
            "CREATE_ENTITY_AND_APPEND_TO_CHANNEL: %s: %s %s",
            entity.platform,
            channel.address,
            parameter,
        )
        channel.add_entity(entity)
        if _check_switch_to_sensor(entity=entity):
            entity.force_to_sensor()


def _check_switch_to_sensor(entity: GenericEntity) -> bool:
    """Check if parameter of a device should be wrapped to a different platform."""
    if entity.device.central.parameter_visibility.parameter_is_un_ignored(
        model=entity.device.model,
        channel_no=entity.channel.no,
        paramset_key=entity.paramset_key,
        parameter=entity.parameter,
    ):
        return False
    for devices, parameter in _SWITCH_ENTITY_TO_SENSOR.items():
        if (
            hms.element_matches_key(
                search_elements=devices,
                compare_with=entity.device.model,
            )
            and entity.parameter == parameter
        ):
            return True
    return False
