"""Here we provide access to the custom device creation functions."""

from hahomematic.devices import climate, cover, light, lock, switch

_ALL_DEVICES = [
    cover.DEVICES,
    climate.DEVICES,
    light.DEVICES,
    lock.DEVICES,
    switch.DEVICES,
]


def get_device_funcs(device_type: str):
    """Return the function to"""

    funcs = []
    for platform_devices in _ALL_DEVICES:
        for name, func in platform_devices.items():
            if "*" in name:
                name = name.replace("*", "").lower()
                if device_type.lower().startswith(name):
                    funcs.append(func)
                    continue
            if name.lower() == device_type.lower():
                funcs.append(func)
                continue
    return funcs


def device_desc_exists(device_type: str) -> bool:
    """Check if device desc exits."""
    return len(get_device_funcs(device_type)) > 0
