"""Code to create the required entities for light entities."""
from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any

from hahomematic.const import HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_COLOR,
    FIELD_CHANNEL_LEVEL,
    FIELD_CHANNEL_STATE,
    FIELD_COLOR,
    FIELD_LEVEL,
    FIELD_STATE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
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
        self,
        device: hm_device.HmDevice,
        address: str,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[str, Any],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.LIGHT,
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
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        ...

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return 0

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_ONOFF

    @property
    def supported_color_modes(self) -> set[str]:
        """Return the supported color modes."""
        return {COLOR_MODE_ONOFF}

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        return 0.0, 0.0

    @abstractmethod
    async def turn_on(
        self, hs_color: tuple[float, float] | None, brightness: int | None
    ) -> None:
        """Turn the light on."""
        ...

    @abstractmethod
    async def turn_off(self) -> None:
        """Turn the light off."""
        ...


class HmDimmer(BaseHmLight):
    """Class for homematic dimmer entities."""

    @property
    def _level(self) -> float | None:
        """Return the dim level of the device."""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float | None:
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
        """Return the supported color modes."""
        return {COLOR_MODE_BRIGHTNESS}

    async def turn_on(
        self, hs_color: tuple[float, float] | None, brightness: int | None
    ) -> None:
        """Turn the light on."""
        # Minimum brightness is 10, otherwise the LED is disabled
        if brightness:
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
    def _state(self) -> bool | None:
        """Return the state of the light."""
        return self._get_entity_value(FIELD_STATE)

    @property
    def _channel_state(self) -> bool | None:
        """Return the channel state of the light."""
        return self._get_entity_value(FIELD_CHANNEL_STATE)

    @property
    def is_on(self) -> bool:
        """Return true if light is on."""
        return self._state is True

    async def turn_on(
        self, hs_color: tuple[float, float] | None, brightness: int | None
    ) -> None:
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
    def _color(self) -> str | None:
        """Return the color of the device."""
        return self._get_entity_value(FIELD_COLOR)

    @property
    def _channel_color(self) -> str | None:
        """Return the channel color of the device."""
        return self._get_entity_value(FIELD_CHANNEL_COLOR)

    @property
    def _level(self) -> float | None:
        """Return the level of the device."""
        return self._get_entity_value(FIELD_LEVEL)

    @property
    def _channel_level(self) -> float | None:
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
        if self._color:
            return self._color_switcher.get(self._color, (0.0, 0.0))
        return 0.0, 0.0

    @property
    def supported_color_modes(self) -> set[str]:
        """Return the supported color modes."""
        return {COLOR_MODE_HS}

    async def turn_on(
        self, hs_color: tuple[float, float] | None, brightness: int | None
    ) -> None:
        """Turn the light on."""
        if hs_color:
            simple_rgb_color = _convert_color(hs_color)
            await self._send_value(FIELD_COLOR, simple_rgb_color)
        # Minimum brightness is 10, otherwise the LED is disabled
        if brightness:
            brightness = max(10, brightness)
            dim_level = brightness / 255.0
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


def _convert_color(color: tuple[float, float] | None) -> str:
    """
    Convert the given color to the reduced color of the device.

    Device contains only 8 colors including white and black,
    so a conversion is required.
    """

    if color is None:
        return "WHITE"

    hue: int = int(color[0])
    saturation: int = int(color[1])
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


def make_ip_dimmer(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip dimmer entities."""
    return make_custom_entity(
        device, address, HmDimmer, EntityDefinition.IP_DIMMER, group_base_channels
    )


def make_rf_dimmer(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic dimmer entities."""
    return make_custom_entity(
        device, address, HmDimmer, EntityDefinition.RF_DIMMER, group_base_channels
    )


def make_ip_light(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic light entities."""
    return make_custom_entity(
        device, address, HmLight, EntityDefinition.IP_LIGHT_SWITCH, group_base_channels
    )


def make_ip_light_bsl(
    device: hm_device.HmDevice, address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates HmIP-BSL entities."""
    return make_custom_entity(
        device, address, IPLightBSL, EntityDefinition.IP_LIGHT_BSL, group_base_channels
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
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
