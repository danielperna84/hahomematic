"""
Here we provide access to the custom device creation functions.
"""

from hahomematic.devices import climate, cover, light

DEVICES = {}
DEVICES.update(cover.DEVICES)
DEVICES.update(climate.DEVICES)
DEVICES.update(light.DEVICES)


def get_device_func(device_type: str):
    """Return the function to"""
    for name, func in DEVICES.items():
        if "*" in name:
            name = name.replace("*", "")
            if device_type.startswith(name):
                return func
        if name.lower() == device_type.lower():
            return func
    return None


def device_desc_exists(device_type: str) -> bool:
    """Check if device desc exits."""
    return get_device_func(device_type) is not None
