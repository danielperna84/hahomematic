"""Module for HaHomematic platforms."""

from __future__ import annotations

import logging
from typing import Final

from hahomematic.caches.visibility import ALLOWED_INTERNAL_PARAMETERS
from hahomematic.const import (
    CLICK_EVENTS,
    DEVICE_ERROR_EVENTS,
    IMPULSE_EVENTS,
    Flag,
    Operations,
    ParamsetKey,
)
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import create_custom_entity_and_append_to_channels
from hahomematic.platforms.event import create_event_and_append_to_channel
from hahomematic.platforms.generic import create_entity_and_append_to_channel

_LOGGER: Final = logging.getLogger(__name__)


def create_entities_and_append_to_device(device: hmd.HmDevice) -> None:
    """Create the entities associated to this device."""
    for channel_address in device.channels:
        if (channel := device.get_channel(channel_address=channel_address)) is None:
            raise HaHomematicException(
                f"CREATE_ENTITIES_AND_APPEND_TO_DEVICE: Channel {channel_address} does not exists.",
            )

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
                model=device.model,
                channel_no=channel.no,
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
                        model=device.model,
                        channel_no=channel.no,
                        paramset_key=paramset_key,
                        parameter=parameter,
                    )
                )

                if paramset_key == ParamsetKey.MASTER:
                    # All MASTER parameters must be un ignored
                    if not parameter_is_un_ignored:
                        continue

                    # required to fix hm master paramset operation values
                    if parameter_is_un_ignored and parameter_data["OPERATIONS"] == 0:
                        parameter_data["OPERATIONS"] = 3

                if parameter_data["OPERATIONS"] & Operations.EVENT and (
                    parameter in CLICK_EVENTS
                    or parameter.startswith(DEVICE_ERROR_EVENTS)
                    or parameter in IMPULSE_EVENTS
                ):
                    create_event_and_append_to_channel(
                        channel=channel,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                if (
                    not parameter_data["OPERATIONS"] & Operations.EVENT
                    and not parameter_data["OPERATIONS"] & Operations.WRITE
                ) or (
                    parameter_data["FLAGS"] & Flag.INTERNAL
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
                    create_entity_and_append_to_channel(
                        channel=channel,
                        paramset_key=paramset_key,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
    create_custom_entity_and_append_to_channels(device=device)
