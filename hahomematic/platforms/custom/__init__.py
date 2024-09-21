"""Module for HaHomematic custom platforms."""

from __future__ import annotations

import importlib
import logging
from typing import Final

from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom.definition import entity_definition_exists, get_custom_configs

_LOGGER: Final = logging.getLogger(__name__)


def create_custom_entity_and_append_to_channels(
    device: hmd.HmDevice,
) -> None:
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
        for custom_config in get_custom_configs(device_type=device.model):
            for channel in device.channels.values():
                custom_config.make_ce_func(channel, custom_config)


def _importlibs() -> None:
    """
    Ensure that all platforms are loaded.

    This ensures that the platform.DEVICES are loaded into ALL_DEVICES,
    and platform.BLACKLISTED_DEVICES are loaded into ALL_BLACKLISTED_DEVICES.
    """
    importlib.import_module("hahomematic.platforms.custom.climate")
    importlib.import_module("hahomematic.platforms.custom.cover")
    importlib.import_module("hahomematic.platforms.custom.light")
    importlib.import_module("hahomematic.platforms.custom.lock")
    importlib.import_module("hahomematic.platforms.custom.siren")
    importlib.import_module("hahomematic.platforms.custom.switch")


_importlibs()
