"""Here we provide access to the custom entity creation functions."""
from __future__ import annotations

from collections.abc import Callable

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
        for name, func in platform_devices.items():
            if "*" in name:
                name = name.replace("*", "").lower()
                if device_type.lower().startswith(name):
                    funcs.append(func)
                    continue
                if sub_type and sub_type.lower().startswith(name):
                    funcs.append(func)
                    continue
            if name.lower() == device_type.lower():
                funcs.append(func)
                continue
            if sub_type and sub_type.lower() == name.lower():
                funcs.append(func)
                continue
    return funcs


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
