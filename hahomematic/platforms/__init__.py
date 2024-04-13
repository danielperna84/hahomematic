"""Module for HaHomematic platforms."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic import support as hms
from hahomematic.caches.visibility import ALLOWED_INTERNAL_PARAMETERS
from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    IMPULSE_EVENTS,
    Description,
    Flag,
    Operations,
    ParamsetKey,
)
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import create_custom_entity_and_append_to_device
from hahomematic.platforms.event import create_event_and_append_to_device
from hahomematic.platforms.generic import create_entity_and_append_to_device

_LOGGER: Final = logging.getLogger(__name__)


def create_entities_and_append_to_device(device: hmd.HmDevice) -> None:
    """Create the entities associated to this device."""
    for channel_address in device.channels:
        channel_no = hms.get_channel_no(channel_address)

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

                if paramset_key == ParamsetKey.MASTER:
                    # All MASTER parameters must be un ignored
                    if not parameter_is_un_ignored:
                        continue

                    # required to fix hm master paramset operation values
                    if parameter_is_un_ignored and parameter_data[Description.OPERATIONS] == 0:
                        parameter_data[Description.OPERATIONS] = 3

                if parameter_data[Description.OPERATIONS] & Operations.EVENT and (
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
                    not parameter_data[Description.OPERATIONS] & Operations.EVENT
                    and not parameter_data[Description.OPERATIONS] & Operations.WRITE
                ) or (
                    parameter_data[Description.FLAGS] & Flag.INTERNAL
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
