"""Here we provide access to the custom entity creation functions."""
from __future__ import annotations

from hahomematic.custom_platforms import climate, cover, light, lock, siren, switch
from hahomematic.custom_platforms.entity_definition import (
    ED_ADDITIONAL_ENTITIES,
    ED_DEFAULT_ENTITIES,
    ED_DEVICE_DEFINITIONS,
    ED_DEVICE_GROUP,
    ED_REPEATABLE_FIELDS,
    ED_VISIBLE_REPEATABLE_FIELDS,
    CustomConfig,
    entity_definition,
)
from hahomematic.helpers import element_matches_key

_ALL_DEVICES = (
    cover.DEVICES,
    climate.DEVICES,
    light.DEVICES,
    lock.DEVICES,
    siren.DEVICES,
    switch.DEVICES,
)

_BLACKLISTED_DEVICES = (
    cover.BLACKLISTED_DEVICES,
    climate.BLACKLISTED_DEVICES,
    light.BLACKLISTED_DEVICES,
    lock.BLACKLISTED_DEVICES,
    siren.BLACKLISTED_DEVICES,
    switch.BLACKLISTED_DEVICES,
)


def get_entity_configs(
    device_type: str,
) -> list[CustomConfig | tuple[CustomConfig, ...]]:
    """Return the entity configs to create custom entities."""
    device_type = device_type.lower().replace("hb-", "hm-")
    funcs = []
    for platform_blacklisted_devices in _BLACKLISTED_DEVICES:
        if element_matches_key(
            search_elements=platform_blacklisted_devices,
            compare_with=device_type,
        ):
            return []

    for platform_devices in _ALL_DEVICES:
        if func := _get_entity_config_by_platform(
            platform_devices=platform_devices,
            device_type=device_type,
        ):
            funcs.append(func)
    return funcs


def _get_entity_config_by_platform(
    platform_devices: dict[str, CustomConfig | tuple[CustomConfig, ...]],
    device_type: str,
) -> CustomConfig | tuple[CustomConfig, ...] | None:
    """Return the entity configs to create custom entities."""
    for d_type, custom_configs in platform_devices.items():
        if device_type.lower() == d_type.lower():
            return custom_configs

    for d_type, custom_configs in platform_devices.items():
        if device_type.lower().startswith(d_type.lower()):
            return custom_configs

    return None


def is_multi_channel_device(device_type: str) -> bool:
    """Return true, if device has multiple channels."""
    channels: list[int] = []
    for entity_configs in get_entity_configs(device_type=device_type):
        if isinstance(entity_configs, CustomConfig):
            channels.extend(entity_configs.channels)
        else:
            for entity_config in entity_configs:
                channels.extend(entity_config.channels)

    return len(channels) > 1


def entity_definition_exists(device_type: str) -> bool:
    """Check if device desc exits."""
    return len(get_entity_configs(device_type)) > 0


def get_required_parameters() -> tuple[str, ...]:
    """Return all required parameters for custom entities."""
    required_parameters: list[str] = []
    for channel in entity_definition[ED_DEFAULT_ENTITIES]:
        required_parameters.extend(entity_definition[ED_DEFAULT_ENTITIES][channel])
    for device in entity_definition[ED_DEVICE_DEFINITIONS]:
        device_def = entity_definition[ED_DEVICE_DEFINITIONS][device][ED_DEVICE_GROUP]
        required_parameters.extend(list(device_def.get(ED_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED_VISIBLE_REPEATABLE_FIELDS, {}).values()))
        required_parameters.extend(list(device_def.get(ED_REPEATABLE_FIELDS, {}).values()))
        for additional_entities in list(
            entity_definition[ED_DEVICE_DEFINITIONS][device]
            .get(ED_ADDITIONAL_ENTITIES, {})
            .values()
        ):
            required_parameters.extend(additional_entities)

    for platform_spec in _ALL_DEVICES:
        for custom_configs in platform_spec.values():
            if isinstance(custom_configs, CustomConfig):
                if extended := custom_configs.extended:
                    required_parameters.extend(extended.required_parameters)
            else:
                for custom_config in custom_configs:
                    if extended := custom_config.extended:
                        required_parameters.extend(extended.required_parameters)

    return tuple(sorted(set(required_parameters)))
