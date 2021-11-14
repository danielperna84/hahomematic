# pylint: disable=line-too-long
"""
Code to create the required entities for light devices.
"""

import logging
from abc import abstractmethod
from typing import Any

from hahomematic.const import HA_PLATFORM_LIGHT
from hahomematic.devices.device_description import (
    DD_PHY_CHANNEL,
    DD_VIRT_CHANNEL,
    FIELD_CHANNEL_COLOR,
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_STATE,
    FIELD_COLOR,
    FIELD_LEVEL,
    FIELD_STATE,
    Devices,
    get_device_entities,
    get_device_groups,
)
from hahomematic.entity import CustomEntity
from hahomematic.helpers import generate_unique_id

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

    # pylint: disable=too-many-arguments
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
    def _level(self) -> float:
        """return the dim level of the device"""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """return the channel level state of the device"""
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

    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        # Minimum brightness is 10, otherwise the led is disabled
        brightness = max(10, brightness)
        dim_level = brightness / 255.0
        await self._send_value(FIELD_LEVEL, dim_level)

    async def async_turn_off(self) -> None:
        """Turn the light off."""
        await self._send_value(FIELD_LEVEL, 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes
        if self._channel_level and self._channel_level != self._level:
            state_attr[ATTR_CHANNEL_LEVEL] = self._channel_level * 255
        return state_attr


class HmLight(BaseHmLight):
    @property
    def _state(self):
        """return the temperature of the device"""
        return self._get_entity_value(FIELD_STATE)

    @property
    def _channel_state(self):
        """return the temperature of the device"""
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

    async def async_turn_on(self, hs_color, brightness) -> None:
        """Turn the light on."""
        await self._send_value(FIELD_STATE, True)

    async def async_turn_off(self) -> None:

        """Turn the light off."""
        await self._send_value(FIELD_STATE, False)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().extra_state_attributes
        if self._channel_state and self._channel_state != self._state:
            state_attr[ATTR_CHANNEL_STATE] = self._channel_state
        return state_attr


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
        """return the color of the device"""
        return self._get_entity_value(FIELD_COLOR)

    @property
    def _channel_color(self):
        """return the channel color of the device"""
        return self._get_entity_value(FIELD_CHANNEL_COLOR)

    @property
    def _level(self) -> float:
        """return the level of the device"""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float:
        """return the channel level state of the device"""
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


def _make_light(device, address, light_class, device_def: Devices):
    """
    Helper to create light entities.
    We use a helper-function to avoid raising exceptions during object-init.
    """
    entities = []
    entity_desc = get_device_entities(device_def)
    for device_desc in get_device_groups(device_def):
        channels = device_desc[DD_PHY_CHANNEL]
        # check if virtual channels should be used
        if device.server.enable_virtual_channels:
            channels += device_desc[DD_VIRT_CHANNEL]
        for channel_no in channels:
            unique_id = generate_unique_id(f"{address}:{channel_no}")
            if unique_id in device.server.hm_entities:
                _LOGGER.debug("_make_light: Skipping %s (already exists)", unique_id)
                continue
            entity = light_class(
                device=device,
                address=address,
                unique_id=unique_id,
                device_desc=device_desc,
                entity_desc=entity_desc,
                channel_no=channel_no,
            )
            if len(entity.data_entities) > 0:
                entity.add_to_collections()
                entities.append(entity)
    return entities


def make_ip_dimmer(device, address):
    """Helper to create homematic ip dimmer entities."""
    return _make_light(device, address, HmDimmer, Devices.IP_DIMMER)


def make_ip_multi_dimmer(device, address):
    """Helper to create homematic ip multi dimmer entities."""
    return _make_light(device, address, HmDimmer, Devices.IP_MULTI_DIMMER)


def make_ip_wired_multi_dimmer(device, address):
    """Helper to create homematic ip multi dimmer entities."""
    return _make_light(device, address, HmDimmer, Devices.IP_WIRED_MULTI_DIMMER)


def make_rf_dimmer(device, address):
    """Helper to create homematic classic dimmer entities."""
    return _make_light(device, address, HmDimmer, Devices.RF_DIMMER)


def make_ip_light(device, address):
    """Helper to create homematic classic light entities."""
    return _make_light(device, address, HmLight, Devices.IP_LIGHT)


def make_ip_light_bsl(device, address):
    """Helper to create HmIP-BSL entities."""
    return _make_light(device, address, IPLightBSL, Devices.IP_LIGHT_BSL)


DEVICES = {
    "HmIP-BSL": make_ip_light_bsl,
    "HmIP-BSM": make_ip_light,
    "HmIP-BDT": make_ip_dimmer,
    "HmIP-FDT": make_ip_dimmer,
    "HmIP-PDT*": make_ip_dimmer,
    "HM-LC-Dim1*": make_rf_dimmer,
    "HM-LC-Dim2*": make_rf_dimmer,
    "HMW-LC-Dim1*": make_rf_dimmer,
    "HM-DW-WM": make_rf_dimmer,
    "HSS-DX": make_rf_dimmer,
    "263 132": make_rf_dimmer,
    "263 133": make_rf_dimmer,
    "263 134": make_rf_dimmer,
    "HmIPW-DRD3": make_ip_wired_multi_dimmer,
    "HmIP-DRDI3": make_ip_multi_dimmer,
}
