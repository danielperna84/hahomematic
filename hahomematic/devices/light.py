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
    FIELD_COLOR,
    FIELD_LEVEL,
    FIELD_RAMP_TIME,
    FIELD_RAMP_TIME_UNIT,
    FIELD_RAMP_TIME_VALUE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.number import HmFloat
from hahomematic.platforms.select import HmSelect

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
SUPPORT_TRANSITION = 32
HM_DIMMER_OFF: float = 0.0

_LOGGER = logging.getLogger(__name__)


class BaseHmLight(CustomEntity):
    """Base class for homematic light entities."""

    def __init__(
        self,
        device: hm_device.HmDevice,
        device_address: str,
        unique_id: str,
        device_enum: EntityDefinition,
        device_def: dict[str, Any],
        entity_def: dict[int, set[str]],
        channel_no: int,
    ):
        super().__init__(
            device=device,
            unique_id=unique_id,
            device_address=device_address,
            device_enum=device_enum,
            device_def=device_def,
            entity_def=entity_def,
            platform=HmPlatform.LIGHT,
            channel_no=channel_no,
        )
        _LOGGER.debug(
            "BaseHmLight.__init__(%s, %s, %s)",
            self._device.interface_id,
            device_address,
            unique_id,
        )

    @property
    def _e_level(self) -> HmFloat:
        """Return the level entity of the device."""
        return self._get_entity(field_name=FIELD_LEVEL, entity_type=HmFloat)

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
    def supported_features(self) -> int:
        """Flag supported features."""
        return 0

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        return 0.0, 0.0

    @abstractmethod
    async def turn_on(
        self,
        hs_color: tuple[float, float] | None,
        brightness: int | None,
        ramp_time: float | None,
    ) -> None:
        """Turn the light on."""
        ...

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._e_level.send_value(HM_DIMMER_OFF)


class CeDimmer(BaseHmLight):
    """Class for homematic dimmer entities."""

    @property
    def _e_ramp_time(self) -> HmAction:
        """Return the ramp time entity device."""
        return self._get_entity(field_name=FIELD_RAMP_TIME, entity_type=HmAction)

    @property
    def _channel_level(self) -> float | None:
        """Return the channel level entity of the device."""
        return self._get_entity_value(field_name=FIELD_CHANNEL_LEVEL)

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._e_level.value is not None and self._e_level.value > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._e_level.value or 0.0) * 255)

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_BRIGHTNESS

    @property
    def supported_color_modes(self) -> set[str]:
        """Return the supported color modes."""
        return {COLOR_MODE_BRIGHTNESS}

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return SUPPORT_TRANSITION

    async def turn_on(
        self,
        hs_color: tuple[float, float] | None,
        brightness: int | None,
        ramp_time: float | None,
    ) -> None:
        """Turn the light on."""
        if ramp_time:
            await self._e_ramp_time.send_value(ramp_time)

        # Minimum brightness is 10, otherwise the LED is disabled
        if brightness:
            brightness = max(10, brightness)
            dim_level = brightness / 255.0
            await self._e_level.send_value(dim_level)

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the light."""
        state_attr = super().attributes
        if (
            self._channel_level
            and self._e_level.value
            and self._channel_level != self._e_level.value
        ):
            state_attr[ATTR_CHANNEL_LEVEL] = self._channel_level * 255
        return state_attr


class CeIpFixedColorLight(BaseHmLight):
    """Class for homematic HmIP-BSL, HmIPW-WRC6 light entities."""

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
    def _e_color(self) -> HmSelect:
        """Return the color entity of the device."""
        return self._get_entity(field_name=FIELD_COLOR, entity_type=HmSelect)

    @property
    def _channel_color(self) -> str | None:
        """Return the channel color of the device."""
        return self._get_entity_value(field_name=FIELD_CHANNEL_COLOR)

    @property
    def _e_level(self) -> HmFloat:
        """Return the level entity of the device."""
        return self._get_entity(field_name=FIELD_LEVEL, entity_type=HmFloat)

    @property
    def _channel_level(self) -> float | None:
        """Return the channel level of the device."""
        return self._get_entity_value(field_name=FIELD_CHANNEL_LEVEL)

    @property
    def _e_ramp_time_unit(self) -> HmAction:
        """Return the ramp time unit entity of the device."""
        return self._get_entity(field_name=FIELD_RAMP_TIME_UNIT, entity_type=HmAction)

    @property
    def _e_ramp_time_value(self) -> HmAction:
        """Return the ramp time value entity of the device."""
        return self._get_entity(field_name=FIELD_RAMP_TIME_VALUE, entity_type=HmAction)

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._e_level.value is not None and self._e_level.value > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._e_level.value or 0.0) * 255)

    @property
    def color_mode(self) -> str:
        """Return the color mode of the light."""
        return COLOR_MODE_HS

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        if self._e_color.value:
            return self._color_switcher.get(self._e_color.value, (0.0, 0.0))
        return 0.0, 0.0

    @property
    def supported_color_modes(self) -> set[str]:
        """Return the supported color modes."""
        return {COLOR_MODE_HS}

    async def turn_on(
        self,
        hs_color: tuple[float, float] | None,
        brightness: int | None,
        ramp_time: float | None,
    ) -> None:
        """Turn the light on."""
        if hs_color:
            simple_rgb_color = _convert_color(hs_color)
            await self._e_color.send_value(simple_rgb_color)
        if ramp_time:
            # ramp_time_unit is 0 == seconds
            await self._e_ramp_time_unit.send_value(0)
            await self._e_ramp_time_value.send_value(ramp_time)
        if brightness:
            # Minimum brightness is 10, otherwise the LED is disabled
            brightness = max(10, brightness)
            dim_level = brightness / 255.0
            await self._e_level.send_value(dim_level)

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().attributes
        if self.is_on:
            state_attr[ATTR_COLOR_NAME] = self._e_color.value
        if self._channel_level and self._channel_level != self._e_level.value:
            state_attr[ATTR_CHANNEL_LEVEL] = self._channel_level * 255
        if self._channel_color and self._channel_color:
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
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic ip dimmer entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeDimmer,
        device_enum=EntityDefinition.IP_DIMMER,
        group_base_channels=group_base_channels,
    )


def make_rf_dimmer(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic dimmer entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeDimmer,
        device_enum=EntityDefinition.RF_DIMMER,
        group_base_channels=group_base_channels,
    )


def make_ip_fixed_color_light(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates fixed color light entities like HmIP-BSL."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeIpFixedColorLight,
        device_enum=EntityDefinition.IP_FIXED_COLOR_LIGHT,
        group_base_channels=group_base_channels,
    )


def make_ip_simple_fixed_color_light(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates simple fixed color light entities like HmIPW-WRC6."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeIpFixedColorLight,
        device_enum=EntityDefinition.IP_SIMPLE_FIXED_COLOR_LIGHT,
        group_base_channels=group_base_channels,
    )


# Case for device model is not relevant
# device_type and sub_type(IP-only) can be used here
DEVICES: dict[str, tuple[Any, list[int]]] = {
    "HmIP-BSL": (make_ip_fixed_color_light, [7, 11]),
    "HmIPW-WRC6": (make_ip_simple_fixed_color_light, [7, 8, 9, 10, 11, 12]),
    "HmIP-BDT": (make_ip_dimmer, [3]),
    "HmIP-FDT": (make_ip_dimmer, [1]),
    "HmIP-PDT*": (make_ip_dimmer, [2]),
    "HMW-LC-Dim1L-DR": (make_rf_dimmer, [3]),
    "HM-DW-WM": (make_rf_dimmer, [1, 2, 3, 4]),
    "HSS-DX": (make_rf_dimmer, [1]),
    "263 132": (make_rf_dimmer, [1]),
    "263 133": (make_rf_dimmer, [1, 2, 3]),
    "263 134": (make_rf_dimmer, [1]),
    "HmIPW-DRD3": (make_ip_dimmer, [1, 5, 9, 13]),
    "HmIP-DRDI3": (make_ip_dimmer, [5, 9, 13]),
    "HmIP-SCTH230": (make_ip_dimmer, [11]),
    "HM-LC-Dim1L-CV-2": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1L-CV": (make_rf_dimmer, [1]),
    "HM-LC-Dim1L-Pl-2": (make_rf_dimmer, [1]),
    "HM-LC-Dim1L-Pl-3": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1L-Pl": (make_rf_dimmer, [1]),
    "HM-LC-Dim1PWM-CV-2": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1PWM-CV": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-CV-2": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-CV": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-DR": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-FM-2": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-FM-LF": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-FM": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-Pl-2": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-Pl-3": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-Pl": (make_rf_dimmer, [1]),
    "HM-LC-Dim1TPBU-FM-2": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1TPBU-FM": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim2L-CV": (make_rf_dimmer, [1, 2]),
    "HM-LC-Dim2L-SM-2": (make_rf_dimmer, [1, 2, 3, 4]),
    "HM-LC-Dim2L-SM": (make_rf_dimmer, [1, 2]),
    "HM-LC-Dim2T-SM-2": (make_rf_dimmer, [1, 2, 3, 4]),
    "HM-LC-Dim2T-SM": (make_rf_dimmer, [1, 2]),
}
