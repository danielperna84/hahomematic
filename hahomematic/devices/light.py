"""Code to create the required entities for light entities."""
from __future__ import annotations

from abc import abstractmethod
import logging
from typing import Any, cast

from hahomematic.const import HM_ARG_ON_TIME, HmPlatform
import hahomematic.device as hm_device
from hahomematic.devices.entity_definition import (
    FIELD_CHANNEL_COLOR,
    FIELD_CHANNEL_LEVEL,
    FIELD_COLOR,
    FIELD_COLOR_LEVEL,
    FIELD_LEVEL,
    FIELD_ON_TIME_UNIT,
    FIELD_ON_TIME_VALUE,
    FIELD_PROGRAM,
    FIELD_RAMP_TIME_UNIT,
    FIELD_RAMP_TIME_VALUE,
    EntityDefinition,
    make_custom_entity,
)
import hahomematic.entity as hm_entity
from hahomematic.entity import CustomEntity
from hahomematic.internal.action import HmAction
from hahomematic.platforms.number import HmFloat, HmInteger
from hahomematic.platforms.select import HmSelect

_LOGGER = logging.getLogger(__name__)

# HM constants
HM_ARG_BRIGHTNESS = "brightness"
HM_ARG_COLOR_NAME = "color_name"
HM_ARG_COLOR_TEMP = "color_temp"
HM_ARG_CHANNEL_COLOR = "channel_color"
HM_ARG_CHANNEL_LEVEL = "channel_level"
HM_ARG_EFFECT = "effect"
HM_ARG_HS_COLOR = "hs_color"
HM_ARG_RAMP_TIME = "ramp_time"

HM_MAX_MIREDS: int = 500
HM_MIN_MIREDS: int = 153

HM_DIMMER_OFF: float = 0.0

TIME_UNIT_SECONDS = 0
TIME_UNIT_MINUTES = 1
TIME_UNIT_HOURS = 2


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
    def _e_on_time_value(self) -> HmAction:
        """Return the on_time entity of the device."""
        return self._get_entity(field_name=FIELD_ON_TIME_VALUE, entity_type=HmAction)

    @property
    def _e_ramp_time_value(self) -> HmAction:
        """Return the ramp time entity device."""
        return self._get_entity(field_name=FIELD_RAMP_TIME_VALUE, entity_type=HmAction)

    @property
    @abstractmethod
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        ...

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return None

    @property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds of this light between 153..500."""
        return None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        return None

    @property
    def supports_brightness(self) -> bool:
        """Flag if light supports brightness."""
        return isinstance(self._e_level, HmFloat)

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return False

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return False

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return False

    @property
    def supports_transition(self) -> bool:
        """Flag if light supports transition."""
        return isinstance(self._e_ramp_time_value, HmAction)

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return None

    async def turn_on(
        self,
        **kwargs: dict[str, Any] | None,
    ) -> None:
        """Turn the light on."""
        if HM_ARG_RAMP_TIME in kwargs:
            ramp_time = float(cast(float, kwargs[HM_ARG_RAMP_TIME]))
            await self.set_ramp_time_value(ramp_time=ramp_time)

        if HM_ARG_ON_TIME in kwargs:
            on_time = float(cast(float, kwargs[HM_ARG_ON_TIME]))
            await self.set_on_time_value(on_time=on_time)

        # Minimum brightness is 10, otherwise the LED is disabled
        if HM_ARG_BRIGHTNESS in kwargs:
            brightness: int = int(cast(int, kwargs[HM_ARG_BRIGHTNESS]))
            brightness = max(10, brightness)
            level = brightness / 255.0
            await self._e_level.send_value(level)

    async def turn_off(self) -> None:
        """Turn the light off."""
        await self._e_level.send_value(HM_DIMMER_OFF)

    async def set_on_time_value(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        if isinstance(self._e_on_time_value, HmAction):
            await self._e_on_time_value.send_value(on_time)

    async def set_ramp_time_value(self, ramp_time: float) -> None:
        """Set the ramp time value in seconds."""
        if isinstance(self._e_ramp_time_value, HmAction):
            await self._e_ramp_time_value.send_value(ramp_time)


class CeDimmer(BaseHmLight):
    """Class for homematic dimmer entities."""

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
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the light."""
        state_attr = super().attributes
        if (
            self._channel_level
            and self._e_level.value
            and self._channel_level != self._e_level.value
        ):
            state_attr[HM_ARG_CHANNEL_LEVEL] = self._channel_level * 255
        return state_attr


class CeColorDimmer(CeDimmer):
    """Class for homematic dimmer with color entities."""

    _effect_list: list[str] = [
        "Off",
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campfire",
        "Waterfall",
        "TV simulation",
    ]

    @property
    def _e_color(self) -> HmInteger:
        """Return the color entity of the device."""
        return self._get_entity(field_name=FIELD_COLOR, entity_type=HmInteger)

    @property
    def _e_effect(self) -> HmInteger:
        """Return the effect entity of the device."""
        return self._get_entity(field_name=FIELD_PROGRAM, entity_type=HmInteger)

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        if self._e_color.value:
            hm_color = self._e_color.value
            if hm_color >= 200:
                # 200 is a special case (white), so we have a saturation of 0.
                # Larger values are undefined. For the sake of robustness we return "white" anyway.
                return 0.0, 0.0

            # For all other colors we assume saturation of 1
            return hm_color / 200, 1
        return 0.0, 0.0

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color temperature."""
        return True

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return True

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._e_effect is not None and self._e_effect.value is not None:
            return self._effect_list[int(self._e_effect.value)]
        return None

    @property
    def effect_list(self) -> list[str] | None:
        """Return the list of supported effects."""
        return self._effect_list

    async def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if HM_ARG_HS_COLOR in kwargs:
            # disable effect
            await self._e_effect.send_value(0)
            hue, saturation = kwargs[HM_ARG_HS_COLOR]
            if saturation < 0.1:  # Special case (white)
                hm_color = 200
            else:
                hm_color = int(round(max(min(hue, 1), 0) * 199))

            await self._e_color.send_value(hm_color)

        if HM_ARG_EFFECT in kwargs:
            effect = str(kwargs[HM_ARG_EFFECT])
            effect_idx = self._effect_list.index(effect)
            if effect_idx is not None:
                await self._e_effect.send_value(effect_idx)

        await super().turn_on(**kwargs)


class CeColorTempDimmer(CeDimmer):
    """Class for homematic dimmer with color temperature entities."""

    @property
    def _e_color_level(self) -> HmFloat:
        """Return the color level entity of the device."""
        return self._get_entity(field_name=FIELD_COLOR_LEVEL, entity_type=HmFloat)

    @property
    def color_temp(self) -> int:
        """Return the color temperature in mireds of this light between 153..500."""
        return int(
            HM_MAX_MIREDS
            - (HM_MAX_MIREDS - HM_MIN_MIREDS) * (self._e_color_level.value or 0.0)
        )

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return True

    async def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""

        if HM_ARG_COLOR_TEMP in kwargs:
            color_level = (HM_MAX_MIREDS - kwargs[HM_ARG_COLOR_TEMP]) / (
                HM_MAX_MIREDS - HM_MIN_MIREDS
            )
            await self._e_color_level.send_value(color_level)

        await super().turn_on(**kwargs)


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
    def _e_on_time_unit(self) -> HmAction:
        """Return the on time unit entity of the device."""
        return self._get_entity(field_name=FIELD_ON_TIME_UNIT, entity_type=HmAction)

    @property
    def _e_ramp_time_unit(self) -> HmAction:
        """Return the ramp time unit entity of the device."""
        return self._get_entity(field_name=FIELD_RAMP_TIME_UNIT, entity_type=HmAction)

    @property
    def is_on(self) -> bool:
        """Return true if dimmer is on."""
        return self._e_level.value is not None and self._e_level.value > 0.0

    @property
    def brightness(self) -> int:
        """Return the brightness of this light between 0..255."""
        return int((self._e_level.value or 0.0) * 255)

    @property
    def hs_color(self) -> tuple[float, float]:
        """Return the hue and saturation color value [float, float]."""
        if self._e_color.value:
            return self._color_switcher.get(self._e_color.value, (0.0, 0.0))
        return 0.0, 0.0

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return True

    async def turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        if HM_ARG_HS_COLOR in kwargs:
            hs_color = kwargs[HM_ARG_HS_COLOR]
            simple_rgb_color = _convert_color(hs_color)
            await self._e_color.send_value(simple_rgb_color)

        await super().turn_on(**kwargs)

    async def set_on_time_value(self, on_time: float) -> None:
        """Set the on time value in seconds."""
        on_time_unit = TIME_UNIT_SECONDS
        if on_time > 16343:
            on_time /= 60
            on_time_unit = TIME_UNIT_MINUTES
        if on_time > 16343:
            on_time /= 60
            on_time_unit = TIME_UNIT_HOURS

        if isinstance(self._e_on_time_value, HmAction) and isinstance(
            self._e_on_time_unit, HmAction
        ):
            await self._e_on_time_value.send_value(on_time_unit)
            await self._e_on_time_value.send_value(float(on_time))

    async def set_ramp_time_value(self, ramp_time: float) -> None:
        """Set the ramp time value in seconds."""
        ramp_time_unit = TIME_UNIT_SECONDS
        if ramp_time > 16343:
            ramp_time /= 60
            ramp_time_unit = TIME_UNIT_MINUTES
        if ramp_time > 16343:
            ramp_time /= 60
            ramp_time_unit = TIME_UNIT_HOURS

        if isinstance(self._e_ramp_time_value, HmAction) and isinstance(
            self._e_ramp_time_unit, HmAction
        ):
            await self._e_ramp_time_value.send_value(ramp_time_unit)
            await self._e_ramp_time_value.send_value(float(ramp_time))

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the notification light sensor."""
        state_attr = super().attributes
        if self.is_on:
            state_attr[HM_ARG_COLOR_NAME] = self._e_color.value
        if self._channel_level and self._channel_level != self._e_level.value:
            state_attr[HM_ARG_CHANNEL_LEVEL] = self._channel_level * 255
        if self._channel_color and self._channel_color:
            state_attr[HM_ARG_CHANNEL_COLOR] = self._channel_color
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


def make_rf_dimmer_color(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic dimmer with color entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeColorDimmer,
        device_enum=EntityDefinition.RF_DIMMER_COLOR,
        group_base_channels=group_base_channels,
    )


def make_rf_dimmer_color_temp(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic dimmer with color temperature entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeColorTempDimmer,
        device_enum=EntityDefinition.RF_DIMMER_COLOR_TEMP,
        group_base_channels=group_base_channels,
    )


def make_rf_dimmer_with_virt_channel(
    device: hm_device.HmDevice, device_address: str, group_base_channels: list[int]
) -> list[hm_entity.BaseEntity]:
    """Creates homematic classic dimmer entities."""
    return make_custom_entity(
        device=device,
        device_address=device_address,
        custom_entity_class=CeDimmer,
        device_enum=EntityDefinition.RF_DIMMER_WITH_VIRT_CHANNEL,
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
    "HmIP-PDT": (make_ip_dimmer, [2]),
    "HMW-LC-Dim1L-DR": (make_rf_dimmer, [3]),
    "HM-DW-WM": (make_rf_dimmer, [1, 2, 3, 4]),
    "HSS-DX": (make_rf_dimmer, [1]),
    "263 132": (make_rf_dimmer, [1]),
    "263 133": (make_rf_dimmer_with_virt_channel, [1]),
    "263 134": (make_rf_dimmer, [1]),
    "HmIPW-DRD3": (make_ip_dimmer, [1, 5, 9]),
    "HmIP-DRDI3": (make_ip_dimmer, [4, 8, 12]),
    "HmIP-SCTH230": (make_ip_dimmer, [11]),
    "HM-LC-Dim1L-CV-2": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1L-CV": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1L-Pl-2": (make_rf_dimmer, [1]),
    "HM-LC-Dim1L-Pl-3": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1L-Pl": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1PWM-CV-2": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1PWM-CV": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-CV-2": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-CV": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-DR": (make_rf_dimmer, [1, 2, 3]),
    "HM-LC-Dim1T-FM-2": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-FM-LF": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-FM": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-Pl-2": (make_rf_dimmer, [1]),
    "HM-LC-Dim1T-Pl-3": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1T-Pl": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1TPBU-FM-2": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim1TPBU-FM": (make_rf_dimmer_with_virt_channel, [1]),
    "HM-LC-Dim2L-CV": (make_rf_dimmer, [1, 2]),
    "HM-LC-Dim2L-SM-2": (make_rf_dimmer, [1, 2, 3, 4, 5, 6]),
    "HM-LC-Dim2L-SM": (make_rf_dimmer, [1, 2, 3, 4, 5, 6]),
    "HM-LC-Dim2T-SM-2": (make_rf_dimmer, [1, 2, 3, 4, 5, 6]),
    "HM-LC-Dim2T-SM": (make_rf_dimmer, [1, 2, 3, 4, 5, 6]),
    "HM-LC-DW-WM": (make_rf_dimmer_color_temp, [1, 3, 5]),
    "HM-LC-RGBW-WM": (make_rf_dimmer_color, [1]),
    "OLIGO.smart.iq.HM": (make_rf_dimmer, [1, 2, 3, 4, 5, 6]),
}

BLACKLISTED_DEVICES: list[str] = []
