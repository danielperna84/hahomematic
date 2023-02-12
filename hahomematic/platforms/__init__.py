"""Module for HaHomematic platforms."""
from __future__ import annotations

import logging

from hahomematic import support as hm_support
from hahomematic.caches.visibility import ALLOWED_INTERNAL_PARAMETERS
from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    FLAG_INTERAL,
    HM_FLAGS,
    HM_OPERATIONS,
    IMPULSE_EVENTS,
    OPERATION_EVENT,
    OPERATION_WRITE,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import create_custom_entity_and_append_to_device
from hahomematic.platforms.event import create_event_and_append_to_device
from hahomematic.platforms.generic import create_entity_and_append_to_device

_LOGGER = logging.getLogger(__name__)


def create_entities_and_append_to_device(device: hmd.HmDevice) -> None:
    """Create the entities associated to this device."""
    for channel_address in device.channels:
        if (channel_no := hm_support.get_channel_no(channel_address)) is None:
            _LOGGER.warning(
                "CREATE_ENTITIES failed: Wrong format of channel_address %s",
                channel_address,
            )
            continue

        if not device.central.paramset_descriptions.get_paramset_keys(
            interface_id=device.interface_id, channel_address=channel_address
        ):
            _LOGGER.debug(
                "CREATE_ENTITIES: Skipping channel %s, missing paramsets",
                channel_address,
            )
            continue
        for paramset_key in device.central.paramset_descriptions.get_paramset_keys(
            interface_id=device.interface_id, channel_address=channel_address
        ):
            if not device.central.parameter_visibility.is_relevant_paramset(
                device_type=device.device_type,
                channel_no=channel_no,
                paramset_key=paramset_key,
            ):
                continue
            for (
                parameter,
                parameter_data,
            ) in device.central.paramset_descriptions.get_paramset_descriptions(
                interface_id=device.interface_id,
                channel_address=channel_address,
                paramset_key=paramset_key,
            ).items():
                parameter_is_un_ignored: bool = (
                    device.central.parameter_visibility.parameter_is_un_ignored(
                        device_type=device.device_type,
                        channel_no=channel_no,
                        paramset_key=paramset_key,
                        parameter=parameter,
                    )
                )
                if parameter_data[HM_OPERATIONS] & OPERATION_EVENT and (
                    parameter in CLICK_EVENTS
                    or parameter.startswith(DEVICE_ERROR_EVENTS)
                    or parameter in IMPULSE_EVENTS
                ):
                    create_event_and_append_to_device(
                        device=device,
                        channel_address=channel_address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                if (
                    not parameter_data[HM_OPERATIONS] & OPERATION_EVENT
                    and not parameter_data[HM_OPERATIONS] & OPERATION_WRITE
                ) or (
                    parameter_data[HM_FLAGS] & FLAG_INTERAL
                    and parameter not in ALLOWED_INTERNAL_PARAMETERS
                    and not parameter_is_un_ignored
                ):
                    _LOGGER.debug(
                        "CREATE_ENTITIES: Skipping %s (no event or internal)",
                        parameter,
                    )
                    continue
                # CLICK_EVENTS are allowed for Buttons
                if parameter not in IMPULSE_EVENTS and (
                    not parameter.startswith(DEVICE_ERROR_EVENTS) or parameter_is_un_ignored
                ):
                    create_entity_and_append_to_device(
                        device=device,
                        channel_address=channel_address,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )

    create_custom_entity_and_append_to_device(device=device)
