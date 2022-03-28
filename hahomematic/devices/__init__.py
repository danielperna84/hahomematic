"""Here we provide access to the custom entity creation functions."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hahomematic.devices import climate, cover, light, lock, siren, switch

_ALL_DEVICES = [
    cover.DEVICES,
    climate.DEVICES,
    light.DEVICES,
    lock.DEVICES,
    siren.DEVICES,
    switch.DEVICES,
]

_BLACKLISTED_DEVICES = [
    cover.BLACKLISTED_DEVICES,
    climate.BLACKLISTED_DEVICES,
    light.BLACKLISTED_DEVICES,
    lock.BLACKLISTED_DEVICES,
    siren.BLACKLISTED_DEVICES,
    switch.BLACKLISTED_DEVICES,
]


def get_device_funcs(
    device_type: str, sub_type: str
) -> list[tuple[Callable, list[int]]]:
    """Return the function to create custom entities"""
    device_type = device_type.lower().replace("hb-", "hm-")
    funcs = []
    for platform_blacklisted_devices in _BLACKLISTED_DEVICES:
        if _is_blacklisted_device_by_platform(
            blacklisted_devices=platform_blacklisted_devices,
            device_type=device_type,
            sub_type=sub_type,
        ):
            return []

    for platform_devices in _ALL_DEVICES:
        if func := _get_device_func_by_platform(
            platform_devices=platform_devices,
            device_type=device_type,
            sub_type=sub_type,
        ):
            funcs.append(func)
    return funcs


def _get_device_func_by_platform(
    platform_devices: dict[str, tuple[Any, list[int]]], device_type: str, sub_type: str
) -> tuple[Callable, list[int]] | None:
    """Return the function to create custom entities"""
    for name, func in platform_devices.items():
        if device_type.lower() == name.lower():
            return func
    for name, func in platform_devices.items():
        if sub_type and sub_type.lower() == name.lower():
            return func
    for name, func in platform_devices.items():
        if device_type.lower().startswith(name.lower()):
            return func

    return None


def _is_blacklisted_device_by_platform(
    blacklisted_devices: list[str], device_type: str, sub_type: str
) -> bool:
    """Return the function to create custom entities"""
    for blacklisted_device in blacklisted_devices:
        if (
            device_type.lower() == blacklisted_device.lower()
            or (sub_type and sub_type.lower() == blacklisted_device.lower())
            or device_type.lower().startswith(blacklisted_device.lower())
        ):
            return True
    return False


def is_multi_channel_device(device_type: str, sub_type: str) -> bool:
    """Return true, if device has multiple channels"""
    channels = []
    funcs = get_device_funcs(device_type=device_type, sub_type=sub_type)
    for func in funcs:
        channels.extend(func[1])

    return len(channels) > 1


def entity_definition_exists(device_type: str, sub_type: str) -> bool:
    """Check if device desc exits."""
    return len(get_device_funcs(device_type, sub_type)) > 0
