"""Module for HaHomematic generic platforms."""
from __future__ import annotations

import logging
from typing import Any

from hahomematic import support as hm_support
from hahomematic.const import (
    BUTTON_ACTIONS,
    CLICK_EVENTS,
    HM_OPERATIONS,
    HM_TYPE,
    HM_VIRTUAL_REMOTE_TYPES,
    OPERATION_WRITE,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
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
        channel_no=hm_support.get_channel_no(address=channel_address),
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
    entity_t: type[hmge.GenericEntity] | None = None
    if parameter_data[HM_OPERATIONS] & OPERATION_WRITE:
        if parameter_data[HM_TYPE] == TYPE_ACTION:
            if parameter_data[HM_OPERATIONS] == OPERATION_WRITE:
                if parameter in BUTTON_ACTIONS or device.device_type in HM_VIRTUAL_REMOTE_TYPES:
                    entity_t = HmButton
                else:
                    entity_t = HmAction
            else:
                if parameter in CLICK_EVENTS:
                    entity_t = HmButton
                else:
                    entity_t = HmSwitch
        else:
            if parameter_data[HM_OPERATIONS] == OPERATION_WRITE:
                entity_t = HmAction
            elif parameter_data[HM_TYPE] == TYPE_BOOL:
                entity_t = HmSwitch
            elif parameter_data[HM_TYPE] == TYPE_ENUM:
                entity_t = HmSelect
            elif parameter_data[HM_TYPE] == TYPE_FLOAT:
                entity_t = HmFloat
            elif parameter_data[HM_TYPE] == TYPE_INTEGER:
                entity_t = HmInteger
            elif parameter_data[HM_TYPE] == TYPE_STRING:
                entity_t = HmText
    else:
        if parameter not in CLICK_EVENTS:
            # Also check, if sensor could be a binary_sensor due to value_list.
            if is_binary_sensor(parameter_data):
                parameter_data[HM_TYPE] = TYPE_BOOL
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
