"""
Here we provide access to the custom device creation functions.
"""

from hahomematic.devices import climate, light

DEVICES = {}
DEVICES.update(climate.DEVICES)
DEVICES.update(light.DEVICES)
