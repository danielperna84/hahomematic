"""Module for HaHomematic custom platforms."""
from __future__ import annotations

import importlib
import logging

from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom.definition import (
    entity_definition_exists,
    get_entity_configs,
)
from hahomematic.platforms.custom.support import CustomConfig

_LOGGER = logging.getLogger(__name__)


def has_custom_entity_definition_by_device(device: hmd.HmDevice) -> bool:
    """Return if custom_entity definition is available for the device."""
    return entity_definition_exists(device.device_type)


def create_custom_entity_and_append_to_device(
    device: hmd.HmDevice,
) -> None:
    """Decides which default platform should be used, and creates the required entities."""
    if entity_definition_exists(device.device_type):
        _LOGGER.debug(
            "CREATE_ENTITIES: Handling custom entity integration: %s, %s, %s",
            device.interface_id,
            device.device_address,
            device.device_type,
        )

        # Call the custom creation function.
        for entity_configs in get_entity_configs(device.device_type):
            if isinstance(entity_configs, CustomConfig):
                entity_configs.func(device, entity_configs.channels, entity_configs.extended)
            else:
                for entity_config in entity_configs:
                    entity_config.func(device, entity_config.channels, entity_config.extended)


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
