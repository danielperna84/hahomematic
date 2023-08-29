"""Module for HaHomematic generic platforms."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic import support as hms
from hahomematic.const import (
    BUTTON_ACTIONS,
    CLICK_EVENTS,
    HM_VIRTUAL_REMOTE_TYPES,
    HmDescription,
    HmOperations,
    HmType,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.generic import entity as hmge
from hahomematic.platforms.generic.action import HmAction
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.generic.button import HmButton
from hahomematic.platforms.generic.number import HmFloat, HmInteger
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch
from hahomematic.platforms.generic.text import HmText
from hahomematic.platforms.support import generate_unique_identifier, is_binary_sensor

_LOGGER = logging.getLogger(__name__)


def create_entity_and_append_to_device(
    device: hmd.HmDevice,
    channel_address: str,
    paramset_key: str,
    parameter: str,
    parameter_data: dict[str, Any],
) -> None:
    """Decides which default platform should be used, and creates the required entities."""
    if device.central.parameter_visibility.parameter_is_ignored(
        device_type=device.device_type,
        channel_no=hms.get_channel_no(address=channel_address),
        paramset_key=paramset_key,
        parameter=parameter,
    ):
        _LOGGER.debug(
            "create_entity_and_append_to_device: Ignoring parameter: %s [%s]",
            parameter,
            channel_address,
        )
        return

    unique_identifier = generate_unique_identifier(
        central=device.central, address=channel_address, parameter=parameter
    )
    if device.central.has_entity(unique_identifier=unique_identifier):
        _LOGGER.debug(
            "create_entity_and_append_to_device: Skipping %s (already exists)",
            unique_identifier,
        )
        return
    _LOGGER.debug(
        "create_entity_and_append_to_device: Creating entity for %s, %s, %s",
        channel_address,
        parameter,
        device.interface_id,
    )
    p_type = parameter_data[HmDescription.TYPE]
    p_operations = parameter_data[HmDescription.OPERATIONS]
    entity_t: type[hmge.GenericEntity] | None = None
    if p_operations & HmOperations.WRITE:
        if p_type == HmType.ACTION:
            if p_operations == HmOperations.WRITE:
                if parameter in BUTTON_ACTIONS or device.device_type in HM_VIRTUAL_REMOTE_TYPES:
                    entity_t = HmButton
                else:
                    entity_t = HmAction
            elif parameter in CLICK_EVENTS:
                entity_t = HmButton
            else:
                entity_t = HmSwitch
        elif p_operations == HmOperations.WRITE:
            entity_t = HmAction
        elif p_type == HmType.BOOL:
            entity_t = HmSwitch
        elif p_type == HmType.ENUM:
            entity_t = HmSelect
        elif p_type == HmType.FLOAT:
            entity_t = HmFloat
        elif p_type == HmType.INTEGER:
            entity_t = HmInteger
        elif p_type == HmType.STRING:
            entity_t = HmText
    elif parameter not in CLICK_EVENTS:
        # Also check, if sensor could be a binary_sensor due to value_list.
        if is_binary_sensor(parameter_data):
            parameter_data[HmDescription.TYPE] = HmType.BOOL
            entity_t = HmBinarySensor
        else:
            entity_t = HmSensor

    if entity_t:
        entity = entity_t(
            device=device,
            unique_identifier=unique_identifier,
            channel_address=channel_address,
            paramset_key=paramset_key,
            parameter=parameter,
            parameter_data=parameter_data,
        )
        _LOGGER.debug(
            "create_entity_and_append_to_device: %s: %s %s",
            entity.platform,
            channel_address,
            parameter,
        )
        device.add_entity(entity)
        if new_platform := device.central.parameter_visibility.wrap_entity(wrapped_entity=entity):
            wrapper_entity = hmge.WrapperEntity(wrapped_entity=entity, new_platform=new_platform)
            device.add_entity(wrapper_entity)
