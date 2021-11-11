# pylint: disable=line-too-long
"""
Code to create the required entities for light devices.
"""

import logging
from typing import Any
from abc import abstractmethod
from hahomematic.const import HA_PLATFORM_LIGHT
from hahomematic.devices.device_description import (
    FIELD_COLOR,
    FIELD_LEVEL,
    FIELD_STATE,
    device_description,
    DD_DEVICE,
    DD_FIELDS,
)
from hahomematic.entity import CustomEntity
from hahomematic.helpers import generate_unique_id

ATTR_BRIGHTNESS = "brightness"
ATTR_COLOR_NAME = "color_name"
COLOR_MODE_ONOFF = "onoff"
COLOR_MODE_BRIGHTNESS = "brightness"  # Must be the only supported mode
COLOR_MODE_HS = "hs"
SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR = 16

_LOGGER = logging.getLogger(__name__)


class BaseHmLight(CustomEntity):

    # pylint: disable=too-many-arguments
    def __init__(self, device, address, unique_id, device_desc, channel_no):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            platform=HA_PLATFORM_LIGHT,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "BaseHmLight.__init__(%s, %s, %s)",
            self._device.interface_id,
            address,
            unique_id,
        )

    @property
    @abstractmethod
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        ...

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return None

    @property
    @abstractmethod
    def supported_color_modes(self) -> set[str]:
        ...

    @abstractmethod
    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        ...

    @abstractmethod
    async def async_turn_off(self) -> None:
        """Turn the light off."""
        ...


class HmDimmer(BaseHmLight):

    @property
    def _level(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._level is not None and self._level > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._level or 0.0) * 255)

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[str]:
        return {COLOR_MODE_BRIGHTNESS}

    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        await self._send_value(FIELD_LEVEL, dim_level)

    async def async_turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_LEVEL, 0)


class HmLight(BaseHmLight):

    @property
    def _state(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_STATE)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_ONOFF

    @property
    def supported_color_modes(self) -> set[str]:
        return {COLOR_MODE_ONOFF}

    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        await self._send_value(FIELD_STATE, True)

    async def async_turn_off(self) -> None:

        """Turn the light off."""
        await self._send_value(FIELD_STATE, False)


class IPLightBSL(BaseHmLight):

    _color_switcher: dict[str, tuple[float, float]] = {
        "WHITE": (0.0, 0.0),
        "RED": (0.0, 100.0),
        "YELLOW": (60.0, 100.0),
        "GREEN": (120.0, 100.0),
        "TURQUOISE": (180.0, 100.0),
        "BLUE": (240.0, 100.0),
        "PURPLE": (300.0, 100.0),
    }

    @property
    def _color(self):
        """return the humidity of the device"""
        return self._get_entity_value(FIELD_COLOR)

    @property
    def _level(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._level is not None and self._level > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._level or 0.0) * 255)

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_HS

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        return self._color_switcher.get(self._color, (0.0, 0.0))

    @property
    def supported_color_modes(self) -> set[str]:
        return {COLOR_MODE_HS}

    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        simple_rgb_color = _convert_color(hs_color)
        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        await self._send_value(FIELD_COLOR, simple_rgb_color)
        await self._send_value(FIELD_LEVEL, dim_level)

    async def async_turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_LEVEL, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes
        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._color
        return state_attr


def _convert_color(color: tuple) -> str:
    """
    Convert the given color to the reduced color of the device.

    Device contains only 8 colors including white and black,
    so a conversion is required.
    """
    if color is None:
        return "WHITE"

    hue = int(color[0])
    saturation = int(color[1])
    if saturation < 5:
        return "WHITE"
    if 30 < hue <= 90:
        return "YELLOW"
    if 90 < hue <= 160:
        return "GREEN"
    if 150 < hue <= 210:
        return "TURQUOISE"
    if 210 < hue <= 270:
        return "BLUE"
    if 270 < hue <= 330:
        return "PURPLE"
    return "RED"


def make_ip_dimmer(device, address):
    """
    Helper to create IPThermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    device_desc = device_description["IPDimmer"]
    entities = []
    for channel_no in device_desc[DD_DEVICE][DD_FIELDS]:
        unique_id = generate_unique_id(f"{address}:{channel_no}")
        entity = HmDimmer(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            channel_no=channel_no,
        )
        entity.add_to_collections()
        entities.append(entity)
    return entities


def make_ip_light(device, address):
    """
    Helper to create IPThermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    device_desc = device_description["IPLight"]
    entities = []
    for channel_no in device_desc[DD_DEVICE][DD_FIELDS]:
        unique_id = generate_unique_id(f"{address}:{channel_no}")
        entity = HmLight(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            channel_no=channel_no,
        )
        entity.add_to_collections()
        entities.append(entity)
    return entities


def make_ip_light_bsl(device, address):
    """
    Helper to create IPThermostat entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    device_desc = device_description["IPLightBSL"]
    entities = []
    for channel_no in device_desc[DD_DEVICE][DD_FIELDS]:
        unique_id = generate_unique_id(f"{address}:{channel_no}")
        entity = IPLightBSL(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            channel_no=channel_no,
        )
        entity.add_to_collections()
        entities.append(entity)
    return entities


DEVICES = {
    "HmIP-BSL": make_ip_light_bsl,
     "HmIP-BSM": make_ip_light,
     "HmIP-BDT": make_ip_dimmer,
     "HmIP-FDT": make_ip_dimmer,
}
