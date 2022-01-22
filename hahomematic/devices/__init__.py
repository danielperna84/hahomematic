"""Here we provide access to the custom entity creation functions."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from hahomematic.devices import climate, cover, light, lock, switch

_ALL_DEVICES = [
    cover.DEVICES,
    climate.DEVICES,
    light.DEVICES,
    lock.DEVICES,
    switch.DEVICES,
]


def get_device_funcs(
    device_type: str, sub_type: str
) -> list[tuple[Callable, list[int]]]:
    """Return the function to create custom entities"""

    funcs = []
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
        if name.lower() == device_type.lower():
            return func
        if sub_type and sub_type.lower() == name.lower():
            return func
        if device_type.lower().startswith(name.lower()):
            return func
    return None


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
