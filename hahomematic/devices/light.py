"""Code to create the required entities for light entities."""

from abc import abstractmethod
import logging
from typing import Any

from hahomematic.const import HA_PLATFORM_LIGHT
from hahomematic.devices.device_description import (
    FIELD_CHANNEL_COLOR,
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_STATE,
    FIELD_COLOR,
    FIELD_LEVEL,
    FIELD_STATE,
    Devices,
    make_custom_entity,
)
from hahomematic.entity import CustomEntity

ATTR_BRIGHTNESS = "brightness"
ATTR_COLOR_NAME = "color_name"
ATTR_CHANNEL_COLOR = "channel_color"
ATTR_CHANNEL_LEVEL = "channel_level"
ATTR_CHANNEL_STATE = "channel_state"
COLOR_MODE_ONOFF = "onoff"
COLOR_MODE_BRIGHTNESS = "brightness"  # Must be the only supported mode
COLOR_MODE_HS = "hs"
SUPPORT_BRIGHTNESS = 1
SUPPORT_COLOR = 16

_LOGGER = logging.getLogger(__name__)


class BaseHmLight(CustomEntity):
    """Base class for homematic light entities."""

    def __init__(
        self, device, address, unique_id, device_desc, entity_desc, channel_no
    ):
        super().__init__(
            device=device,
            address=address,
            unique_id=unique_id,
            device_desc=device_desc,
            entity_desc=entity_desc,
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
        """Return true if light is on."""
        ...

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return None

    @property
    @abstractmethod
    def supported_color_modes(self) -> set[str]:
        """Return the supported color_modes."""
        ...

    @abstractmethod
    async def turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        ...

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the light off."""
        ...


class HmDimmer(BaseHmLight):
    """Class for homematic dimmer entities."""

    @property
    def _level(self) -> float:
        """Return the dim level of the device."""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """Return the channel level of the device."""
        return self._get_entity_value(FIELD_CHANNEL_LEVEL)

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

    async def turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        await self._send_value(FIELD_LEVEL, dim_level)

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_LEVEL, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the light."""
        state_attr = super().extra_state_attributes
        if self._channel_level and self._channel_level != self._level:
            state_attr[ATTR_CHANNEL_LEVEL] = self._channel_level * 255
        return state_attr


class HmLight(BaseHmLight):
    """Class for homematic light entities."""

    @property
    def _state(self):
        """Return the temperature of the light."""
        return self._get_entity_value(FIELD_STATE)

    @property
    def _channel_state(self):
        """Return the temperature of the light."""
        return self._get_entity_value(FIELD_CHANNEL_STATE)

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

    async def turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        await self._send_value(FIELD_STATE, True)

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_STATE, False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the light."""
        state_attr = super().extra_state_attributes
        if self._channel_state and self._channel_state != self._state:
            state_attr[ATTR_CHANNEL_STATE] = self._channel_state
        return state_attr


class IPLightBSL(BaseHmLight):
    """Class for homematic HmIP-BSL light entities."""

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
        """Return the color of the device."""
        return self._get_entity_value(FIELD_COLOR)

    @property
    def _channel_color(self):
        """Return the channel color of the device."""
        return self._get_entity_value(FIELD_CHANNEL_COLOR)

    @property
    def _level(self) -> float:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """Return the channel level state of the device."""
        return self._get_entity_value(FIELD_CHANNEL_LEVEL)

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

    async def turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        simple_rgb_color = _convert_color(hs_color)
        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        await self._send_value(FIELD_COLOR, simple_rgb_color)
        await self._send_value(FIELD_LEVEL, dim_level)

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_LEVEL, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes
        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._color
        if self._channel_level and self._channel_level != self._level:
            state_attr[ATTR_CHANNEL_LEVEL] = self._channel_level * 255
        if self._channel_color and self._channel_color != self._color:
            state_attr[ATTR_CHANNEL_COLOR] = self._channel_color
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
        bsl_color = "WHITE"
    elif 30 < hue <= 90:
        bsl_color = "YELLOW"
    elif 90 < hue <= 160:
        bsl_color = "GREEN"
    elif 150 < hue <= 210:
        bsl_color = "TURQUOISE"
    elif 210 < hue <= 270:
        bsl_color = "BLUE"
    elif 270 < hue <= 330:
        bsl_color = "PURPLE"
    else:
        bsl_color = "RED"
    return bsl_color


def make_ip_dimmer(device, address, group_base_channels: [int]):
    """Creates homematic ip dimmer entities."""
    return make_custom_entity(
        device, address, HmDimmer, Devices.IP_DIMMER, group_base_channels
    )


def make_rf_dimmer(device, address, group_base_channels: [int]):
    """Creates homematic classic dimmer entities."""
    return make_custom_entity(
        device, address, HmDimmer, Devices.RF_DIMMER, group_base_channels
    )


def make_ip_light(device, address, group_base_channels: [int]):
    """Creates homematic classic light entities."""
    return make_custom_entity(
        device, address, HmLight, Devices.IP_LIGHT_SWITCH, group_base_channels
    )


def make_ip_light_bsl(device, address, group_base_channels: [int]):
    """Creates HmIP-BSL entities."""
    return make_custom_entity(
        device, address, IPLightBSL, Devices.IP_LIGHT_BSL, group_base_channels
    )


DEVICES = {
    "HmIP-BSL": (make_ip_light_bsl, [7, 11]),
    "HmIP-BSM": (make_ip_light, [3]),
    "HmIP-BDT": (make_ip_dimmer, [3]),
    "HmIP-FDT": (make_ip_dimmer, [1]),
    "HmIP-PDT*": (make_ip_dimmer, [2]),
    "HM-LC-Dim1*": (make_rf_dimmer, []),
    "HM-LC-Dim2*": (make_rf_dimmer, []),
    "HMW-LC-Dim1*": (make_rf_dimmer, []),
    "HM-DW-WM": (make_rf_dimmer, []),
    "HSS-DX": (make_rf_dimmer, []),
    "263 132": (make_rf_dimmer, []),
    "263 133": (make_rf_dimmer, []),
    "263 134": (make_rf_dimmer, []),
    "HmIPW-DRD3": (make_ip_dimmer, [1, 5, 9, 13]),
    "HmIP-DRDI3": (make_ip_dimmer, [5, 9, 13]),
}
