"""
Module for entities implemented using the light platform.

See https://www.home-assistant.io/integrations/light/.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum, StrEnum
import math
from typing import Any, Final, TypedDict, Unpack

from hahomematic.const import EntityUsage, HmPlatform, Parameter
from hahomematic.platforms import device as hmd
from hahomematic.platforms.custom import definition as hmed
from hahomematic.platforms.custom.const import DeviceProfile, Field
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.custom.support import CustomConfig, ExtendedConfig
from hahomematic.platforms.decorators import state_property
from hahomematic.platforms.entity import CallParameterCollector, bind_collector
from hahomematic.platforms.generic import (
    GenericEntity,
    HmAction,
    HmFloat,
    HmInteger,
    HmSelect,
    HmSensor,
)
from hahomematic.platforms.support import OnTimeMixin

_DIMMER_OFF: Final = 0.0
_EFFECT_OFF: Final = "Off"
_MAX_BRIGHTNESS: Final = 255.0
_MAX_MIREDS: Final = 500
_MIN_BRIGHTNESS: Final = 0.0
_MIN_MIREDS: Final = 153


class _DeviceOperationMode(StrEnum):
    """Enum with device operation modes."""

    PWM = "4_PWM"
    RGB = "RGB"
    RGBW = "RGBW"
    TUNABLE_WHITE = "2_TUNABLE_WHITE"


class _ColorBehaviour(StrEnum):
    """Enum with color behaviours."""

    DO_NOT_CARE = "DO_NOT_CARE"
    OFF = "OFF"
    OLD_VALUE = "OLD_VALUE"
    ON = "ON"


class _FixedColor(StrEnum):
    """Enum with colors."""

    BLACK = "BLACK"
    BLUE = "BLUE"
    DO_NOT_CARE = "DO_NOT_CARE"
    GREEN = "GREEN"
    OLD_VALUE = "OLD_VALUE"
    PURPLE = "PURPLE"
    RED = "RED"
    TURQUOISE = "TURQUOISE"
    WHITE = "WHITE"
    YELLOW = "YELLOW"


class _StateChangeArg(StrEnum):
    """Enum with light state change arguments."""

    BRIGHTNESS = "brightness"
    COLOR_TEMP = "color_temp"
    EFFECT = "effect"
    HS_COLOR = "hs_color"
    OFF = "off"
    ON = "on"
    ON_TIME = "on_time"
    RAMP_TIME = "ramp_time"


class _TimeUnit(IntEnum):
    """Enum with time units."""

    SECONDS = 0
    MINUTES = 1
    HOURS = 2


_NO_COLOR: Final = (
    _FixedColor.BLACK,
    _FixedColor.DO_NOT_CARE,
    _FixedColor.OLD_VALUE,
)

_EXCLUDE_FROM_COLOR_BEHAVIOUR: Final = (
    _ColorBehaviour.DO_NOT_CARE,
    _ColorBehaviour.OFF,
    _ColorBehaviour.OLD_VALUE,
)

_OFF_COLOR_BEHAVIOUR: Final = (
    _ColorBehaviour.DO_NOT_CARE,
    _ColorBehaviour.OFF,
    _ColorBehaviour.OLD_VALUE,
)

_FIXED_COLOR_SWITCHER: Mapping[str, tuple[float, float]] = {
    _FixedColor.WHITE: (0.0, 0.0),
    _FixedColor.RED: (0.0, 100.0),
    _FixedColor.YELLOW: (60.0, 100.0),
    _FixedColor.GREEN: (120.0, 100.0),
    _FixedColor.TURQUOISE: (180.0, 100.0),
    _FixedColor.BLUE: (240.0, 100.0),
    _FixedColor.PURPLE: (300.0, 100.0),
}


class LightOnArgs(TypedDict, total=False):
    """Matcher for the light turn on arguments."""

    brightness: int
    color_temp: int
    effect: str
    hs_color: tuple[float, float]
    on_time: float
    ramp_time: float


class LightOffArgs(TypedDict, total=False):
    """Matcher for the light turn off arguments."""

    ramp_time: float


class CeDimmer(CustomEntity, OnTimeMixin):
    """Base class for HomeMatic light entities."""

    _platform = HmPlatform.LIGHT

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        OnTimeMixin.__init__(self)
        super()._init_entity_fields()
        self._e_level: HmFloat = self._get_entity(field=Field.LEVEL, entity_type=HmFloat)
        self._e_channel_level: HmSensor[float | None] = self._get_entity(
            field=Field.CHANNEL_LEVEL, entity_type=HmSensor[float | None]
        )
        self._e_on_time_value: HmAction = self._get_entity(
            field=Field.ON_TIME_VALUE, entity_type=HmAction
        )
        self._e_ramp_time_value: HmAction = self._get_entity(
            field=Field.RAMP_TIME_VALUE, entity_type=HmAction
        )

    @state_property
    def is_on(self) -> bool | None:
        """Return true if dimmer is on."""
        return self._e_level.value is not None and self._e_level.value > _DIMMER_OFF

    @state_property
    def brightness(self) -> int | None:
        """Return the brightness of this light between min/max brightness."""
        return int((self._e_level.value or _MIN_BRIGHTNESS) * _MAX_BRIGHTNESS)

    @property
    def brightness_pct(self) -> int | None:
        """Return the brightness in percent of this light."""
        return int((self._e_level.value or _MIN_BRIGHTNESS) * 100)

    @property
    def channel_brightness(self) -> int | None:
        """Return the channel_brightness of this light between min/max brightness."""
        if self._e_channel_level.value is not None:
            return int(self._e_channel_level.value * _MAX_BRIGHTNESS)
        return None

    @property
    def channel_brightness_pct(self) -> int | None:
        """Return the channel_brightness in percent of this light."""
        if self._e_channel_level.value is not None:
            return int(self._e_channel_level.value * 100)
        return None

    @state_property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds of this light between min/max mireds."""
        return None

    @state_property
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
        return self.color_temp is not None

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return self.effects is not None and len(self.effects) > 0

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return self.hs_color is not None

    @property
    def supports_transition(self) -> bool:
        """Flag if light supports transition."""
        return isinstance(self._e_ramp_time_value, HmAction)

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return None

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if ramp_time := kwargs.get("ramp_time"):
            await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)
        if (on_time := kwargs.get("on_time")) or (on_time := self.get_on_time_and_cleanup()):
            await self._set_on_time_value(on_time=on_time, collector=collector)

        if not (brightness := kwargs.get("brightness", self.brightness)):
            brightness = int(_MAX_BRIGHTNESS)
        level = brightness / _MAX_BRIGHTNESS
        await self._e_level.send_value(value=level, collector=collector)

    @bind_collector()
    async def turn_off(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]
    ) -> None:
        """Turn the light off."""
        if not self.is_state_change(off=True, **kwargs):
            return
        if ramp_time := kwargs.get("ramp_time"):
            await self._set_ramp_time_off_value(ramp_time=ramp_time, collector=collector)

        await self._e_level.send_value(value=_DIMMER_OFF, collector=collector)

    @bind_collector()
    async def _set_on_time_value(
        self, on_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the on time value in seconds."""
        await self._e_on_time_value.send_value(value=on_time, collector=collector)

    async def _set_ramp_time_on_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        await self._e_ramp_time_value.send_value(value=ramp_time, collector=collector)

    async def _set_ramp_time_off_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        await self._set_ramp_time_on_value(ramp_time=ramp_time, collector=collector)

    def is_state_change(self, **kwargs: Any) -> bool:
        """Check if the state changes due to kwargs."""
        if (
            kwargs.get(_StateChangeArg.ON) is not None
            and self.is_on is not True
            and len(kwargs) == 1
        ):
            return True
        if (
            kwargs.get(_StateChangeArg.OFF) is not None
            and self.is_on is not False
            and len(kwargs) == 1
        ):
            return True
        if (
            brightness := kwargs.get(_StateChangeArg.BRIGHTNESS)
        ) is not None and brightness != self.brightness:
            return True
        if (
            hs_color := kwargs.get(_StateChangeArg.HS_COLOR)
        ) is not None and hs_color != self.hs_color:
            return True
        if (
            color_temp := kwargs.get(_StateChangeArg.COLOR_TEMP)
        ) is not None and color_temp != self.color_temp:
            return True
        if (effect := kwargs.get(_StateChangeArg.EFFECT)) is not None and effect != self.effect:
            return True
        if kwargs.get(_StateChangeArg.RAMP_TIME) is not None:
            return True
        if kwargs.get(_StateChangeArg.ON_TIME) is not None:
            return True
        return super().is_state_change(**kwargs)


class CeColorDimmer(CeDimmer):
    """Class for HomeMatic dimmer with color entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_color: HmInteger = self._get_entity(field=Field.COLOR, entity_type=HmInteger)

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if (color := self._e_color.value) is not None:
            if color >= 200:
                # 200 is a special case (white), so we have a saturation of 0.
                # Larger values are undefined.
                # For the sake of robustness we return "white" anyway.
                return 0.0, 0.0

            # For all other colors we assume saturation of 1
            return color / 200 * 360, 100
        return 0.0, 0.0

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            khue, ksaturation = hs_color
            hue = khue / 360
            saturation = ksaturation / 100
            color = 200 if saturation < 0.1 else int(round(max(min(hue, 1), 0) * 199))
            await self._e_color.send_value(value=color, collector=collector)
        await super().turn_on(collector=collector, **kwargs)


class CeColorDimmerEffect(CeColorDimmer):
    """Class for HomeMatic dimmer with color entities."""

    _effects: tuple[str, ...] = (
        _EFFECT_OFF,
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campfire",
        "Waterfall",
        "TV simulation",
    )

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_effect: HmInteger = self._get_entity(field=Field.PROGRAM, entity_type=HmInteger)

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        if self._e_effect.value is not None:
            return self._effects[int(self._e_effect.value)]
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._effects

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return

        if "effect" not in kwargs and self.supports_effects and self.effect != _EFFECT_OFF:
            await self._e_effect.send_value(value=0, collector=collector, collector_order=5)

        if (
            self.supports_effects
            and (effect := kwargs.get("effect")) is not None
            and (effect_idx := self._effects.index(effect)) is not None
        ):
            await self._e_effect.send_value(
                value=effect_idx, collector=collector, collector_order=95
            )

        await super().turn_on(collector=collector, **kwargs)


class CeColorTempDimmer(CeDimmer):
    """Class for HomeMatic dimmer with color temperature entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_color_level: HmFloat = self._get_entity(
            field=Field.COLOR_LEVEL, entity_type=HmFloat
        )

    @state_property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds of this light between min/max mireds."""
        return int(_MAX_MIREDS - (_MAX_MIREDS - _MIN_MIREDS) * (self._e_color_level.value or 0.0))

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (color_temp := kwargs.get("color_temp")) is not None:
            color_level = (_MAX_MIREDS - color_temp) / (_MAX_MIREDS - _MIN_MIREDS)
            await self._e_color_level.send_value(value=color_level, collector=collector)

        await super().turn_on(collector=collector, **kwargs)


class CeIpRGBWLight(CeDimmer):
    """Class for HomematicIP HmIP-RGBW light entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_activity_state: HmSensor[str | None] = self._get_entity(
            field=Field.DIRECTION, entity_type=HmSensor[str | None]
        )
        self._e_color_temperature_kelvin: HmInteger = self._get_entity(
            field=Field.COLOR_TEMPERATURE, entity_type=HmInteger
        )
        self._e_device_operation_mode: HmSelect = self._get_entity(
            field=Field.DEVICE_OPERATION_MODE, entity_type=HmSelect
        )
        self._e_on_time_unit: HmAction = self._get_entity(
            field=Field.ON_TIME_UNIT, entity_type=HmAction
        )
        self._e_effect: HmAction = self._get_entity(field=Field.EFFECT, entity_type=HmAction)
        self._e_hue: HmInteger = self._get_entity(field=Field.HUE, entity_type=HmInteger)
        self._e_ramp_time_to_off_unit: HmAction = self._get_entity(
            field=Field.RAMP_TIME_TO_OFF_UNIT, entity_type=HmAction
        )
        self._e_ramp_time_to_off_value: HmAction = self._get_entity(
            field=Field.RAMP_TIME_TO_OFF_VALUE, entity_type=HmAction
        )
        self._e_ramp_time_unit: HmAction = self._get_entity(
            field=Field.RAMP_TIME_UNIT, entity_type=HmAction
        )
        self._e_saturation: HmFloat = self._get_entity(field=Field.SATURATION, entity_type=HmFloat)

    @state_property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds of this light between min/max mireds."""
        if not self._e_color_temperature_kelvin.value:
            return None
        return math.floor(1000000 / self._e_color_temperature_kelvin.value)

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._e_hue.value is not None and self._e_saturation.value is not None:
            return self._e_hue.value, self._e_saturation.value * 100
        return None

    @property
    def _relevant_entities(self) -> tuple[GenericEntity, ...]:
        """Returns the list of relevant entities. To be overridden by subclasses."""
        if self._e_device_operation_mode.value == _DeviceOperationMode.RGBW:
            return self._e_hue, self._e_level, self._e_saturation, self._e_color_temperature_kelvin
        if self._e_device_operation_mode.value == _DeviceOperationMode.RGB:
            return self._e_hue, self._e_level, self._e_saturation
        if self._e_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE:
            return self._e_level, self._e_color_temperature_kelvin
        return (self._e_level,)

    @property
    def supports_color_temperature(self) -> bool:
        """Flag if light supports color temperature."""
        return self._e_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE

    @property
    def supports_effects(self) -> bool:
        """Flag if light supports effects."""
        return (
            self._e_device_operation_mode.value != _DeviceOperationMode.PWM
            and self.effects is not None
            and len(self.effects) > 0
        )

    @property
    def supports_hs_color(self) -> bool:
        """Flag if light supports color."""
        return self._e_device_operation_mode.value in (
            _DeviceOperationMode.RGBW,
            _DeviceOperationMode.RGB,
        )

    @property
    def usage(self) -> EntityUsage:
        """
        Return the entity usage.

        Avoid creating entities that are not usable in selected device operation mode.
        """
        if (
            self._e_device_operation_mode.value
            in (_DeviceOperationMode.RGB, _DeviceOperationMode.RGBW)
            and self._channel.no in (2, 3, 4)
        ) or (
            self._e_device_operation_mode.value == _DeviceOperationMode.TUNABLE_WHITE
            and self._channel.no in (3, 4)
        ):
            return EntityUsage.NO_CREATE
        return self._get_entity_usage()

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._e_effect.values or ()

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            hue, ksaturation = hs_color
            saturation = ksaturation / 100
            await self._e_hue.send_value(value=int(hue), collector=collector)
            await self._e_saturation.send_value(value=saturation, collector=collector)
        if color_temp := kwargs.get("color_temp"):
            color_temp_kelvin = math.floor(1000000 / color_temp)
            await self._e_color_temperature_kelvin.send_value(
                value=color_temp_kelvin, collector=collector
            )
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            # 111600 is a special value for NOT_USED
            await self._set_on_time_value(on_time=111600, collector=collector)
        if self.supports_effects and (effect := kwargs.get("effect")) is not None:
            await self._e_effect.send_value(value=effect, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    @bind_collector()
    async def turn_off(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOffArgs]
    ) -> None:
        """Turn the light off."""
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            # 111600 is a special value for NOT_USED
            await self._set_on_time_value(on_time=111600, collector=collector)
        await super().turn_off(collector=collector, **kwargs)

    @bind_collector()
    async def _set_on_time_value(
        self, on_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit is not None:
            await self._e_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._e_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._e_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._e_ramp_time_value.send_value(value=float(ramp_time), collector=collector)

    async def _set_ramp_time_off_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit is not None:
            await self._e_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._e_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


class CeIpDrgDaliLight(CeDimmer):
    """Class for HomematicIP HmIP-DRG-DALI light entities."""

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_color_temperature_kelvin: HmInteger = self._get_entity(
            field=Field.COLOR_TEMPERATURE, entity_type=HmInteger
        )
        self._e_on_time_unit: HmAction = self._get_entity(
            field=Field.ON_TIME_UNIT, entity_type=HmAction
        )
        self._e_effect: HmAction = self._get_entity(field=Field.EFFECT, entity_type=HmAction)
        self._e_hue: HmInteger = self._get_entity(field=Field.HUE, entity_type=HmInteger)
        self._e_ramp_time_to_off_unit: HmAction = self._get_entity(
            field=Field.RAMP_TIME_TO_OFF_UNIT, entity_type=HmAction
        )
        self._e_ramp_time_to_off_value: HmAction = self._get_entity(
            field=Field.RAMP_TIME_TO_OFF_VALUE, entity_type=HmAction
        )
        self._e_ramp_time_unit: HmAction = self._get_entity(
            field=Field.RAMP_TIME_UNIT, entity_type=HmAction
        )
        self._e_saturation: HmFloat = self._get_entity(field=Field.SATURATION, entity_type=HmFloat)

    @state_property
    def color_temp(self) -> int | None:
        """Return the color temperature in mireds of this light between min/max mireds."""
        if not self._e_color_temperature_kelvin.value:
            return None
        return math.floor(1000000 / self._e_color_temperature_kelvin.value)

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if self._e_hue.value is not None and self._e_saturation.value is not None:
            return self._e_hue.value, self._e_saturation.value * 100
        return None

    @property
    def _relevant_entities(self) -> tuple[GenericEntity, ...]:
        """Returns the list of relevant entities. To be overridden by subclasses."""
        return (self._e_level,)

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._e_effect.values or ()

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            hue, ksaturation = hs_color
            saturation = ksaturation / 100
            await self._e_hue.send_value(value=int(hue), collector=collector)
            await self._e_saturation.send_value(value=saturation, collector=collector)
        if color_temp := kwargs.get("color_temp"):
            color_temp_kelvin = math.floor(1000000 / color_temp)
            await self._e_color_temperature_kelvin.send_value(
                value=color_temp_kelvin, collector=collector
            )
        if kwargs.get("on_time") is None and kwargs.get("ramp_time"):
            # 111600 is a special value for NOT_USED
            await self._set_on_time_value(on_time=111600, collector=collector)
        if self.supports_effects and (effect := kwargs.get("effect")) is not None:
            await self._e_effect.send_value(value=effect, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    @bind_collector()
    async def _set_on_time_value(
        self, on_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit:
            await self._e_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._e_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._e_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._e_ramp_time_value.send_value(value=float(ramp_time), collector=collector)

    async def _set_ramp_time_off_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._e_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._e_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


class CeIpFixedColorLight(CeDimmer):
    """Class for HomematicIP HmIP-BSL light entities."""

    @state_property
    def color_name(self) -> str | None:
        """Return the name of the color."""
        return self._e_color.value

    @property
    def channel_color_name(self) -> str | None:
        """Return the name of the channel color."""
        return self._e_channel_color.value

    def _init_entity_fields(self) -> None:
        """Init the entity fields."""
        super()._init_entity_fields()
        self._e_color: HmSelect = self._get_entity(field=Field.COLOR, entity_type=HmSelect)
        self._e_channel_color: HmSensor[str | None] = self._get_entity(
            field=Field.CHANNEL_COLOR, entity_type=HmSensor[str | None]
        )
        self._e_on_time_unit: HmAction = self._get_entity(
            field=Field.ON_TIME_UNIT, entity_type=HmAction
        )
        self._e_ramp_time_unit: HmAction = self._get_entity(
            field=Field.RAMP_TIME_UNIT, entity_type=HmAction
        )
        self._e_effect: HmSelect = self._get_entity(
            field=Field.COLOR_BEHAVIOUR, entity_type=HmSelect
        )
        self._effect_list = (
            tuple(
                str(item)
                for item in self._e_effect.values
                if item not in _EXCLUDE_FROM_COLOR_BEHAVIOUR
            )
            if (self._e_effect and self._e_effect.values)
            else ()
        )

    @state_property
    def effect(self) -> str | None:
        """Return the current effect."""
        if (effect := self._e_effect.value) is not None and effect in self._effect_list:
            return effect
        return None

    @state_property
    def effects(self) -> tuple[str, ...] | None:
        """Return the supported effects."""
        return self._effect_list

    @state_property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        if (
            self._e_color.value is not None
            and (hs_color := _FIXED_COLOR_SWITCHER.get(self._e_color.value)) is not None
        ):
            return hs_color
        return 0.0, 0.0

    @property
    def channel_hs_color(self) -> tuple[float, float] | None:
        """Return the channel hue and saturation color value [float, float]."""
        if self._e_channel_color.value is not None:
            return _FIXED_COLOR_SWITCHER.get(self._e_channel_color.value, (0.0, 0.0))
        return None

    @bind_collector()
    async def turn_on(
        self, collector: CallParameterCollector | None = None, **kwargs: Unpack[LightOnArgs]
    ) -> None:
        """Turn the light on."""
        if not self.is_state_change(on=True, **kwargs):
            return
        if (hs_color := kwargs.get("hs_color")) is not None:
            simple_rgb_color = _convert_color(hs_color)
            await self._e_color.send_value(value=simple_rgb_color, collector=collector)
        elif self.color_name in _NO_COLOR:
            await self._e_color.send_value(value=_FixedColor.WHITE, collector=collector)
        if (effect := kwargs.get("effect")) is not None and effect in self._effect_list:
            await self._e_effect.send_value(value=effect, collector=collector)
        elif self._e_effect.value not in self._effect_list:
            await self._e_effect.send_value(value=_ColorBehaviour.ON, collector=collector)
        elif (color_behaviour := self._e_effect.value) is not None:
            await self._e_effect.send_value(value=color_behaviour, collector=collector)

        await super().turn_on(collector=collector, **kwargs)

    @bind_collector()
    async def _set_on_time_value(
        self, on_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the on time value in seconds."""
        on_time, on_time_unit = _recalc_unit_timer(time=on_time)
        if on_time_unit:
            await self._e_on_time_unit.send_value(value=on_time_unit, collector=collector)
        await self._e_on_time_value.send_value(value=float(on_time), collector=collector)

    async def _set_ramp_time_on_value(
        self, ramp_time: float, collector: CallParameterCollector | None = None
    ) -> None:
        """Set the ramp time value in seconds."""
        ramp_time, ramp_time_unit = _recalc_unit_timer(time=ramp_time)
        if ramp_time_unit:
            await self._e_ramp_time_unit.send_value(value=ramp_time_unit, collector=collector)
        await self._e_ramp_time_value.send_value(value=float(ramp_time), collector=collector)


def _recalc_unit_timer(time: float) -> tuple[float, int | None]:
    """Recalculate unit and value of timer."""
    ramp_time_unit = _TimeUnit.SECONDS
    if time == 111600:
        return time, None
    if time > 16343:
        time /= 60
        ramp_time_unit = _TimeUnit.MINUTES
    if time > 16343:
        time /= 60
        ramp_time_unit = _TimeUnit.HOURS
    return time, ramp_time_unit


def _convert_color(color: tuple[float, float]) -> str:
    """
    Convert the given color to the reduced color of the device.

    Device contains only 8 colors including white and black,
    so a conversion is required.
    """
    hue: int = int(color[0])
    if int(color[1]) < 5:
        return _FixedColor.WHITE
    if 30 < hue <= 90:
        return _FixedColor.YELLOW
    if 90 < hue <= 150:
        return _FixedColor.GREEN
    if 150 < hue <= 210:
        return _FixedColor.TURQUOISE
    if 210 < hue <= 270:
        return _FixedColor.BLUE
    if 270 < hue <= 330:
        return _FixedColor.PURPLE
    return _FixedColor.RED


def make_ip_dimmer(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomematicIP dimmer entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeDimmer,
        device_profile=DeviceProfile.IP_DIMMER,
        custom_config=custom_config,
    )


def make_rf_dimmer(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeDimmer,
        device_profile=DeviceProfile.RF_DIMMER,
        custom_config=custom_config,
    )


def make_rf_dimmer_color(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with color entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeColorDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_fixed(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with fixed color entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeColorDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR_FIXED,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_effect(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer and effect with color entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeColorDimmerEffect,
        device_profile=DeviceProfile.RF_DIMMER_COLOR,
        custom_config=custom_config,
    )


def make_rf_dimmer_color_temp(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer with color temperature entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeColorTempDimmer,
        device_profile=DeviceProfile.RF_DIMMER_COLOR_TEMP,
        custom_config=custom_config,
    )


def make_rf_dimmer_with_virt_channel(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create HomeMatic classic dimmer entities."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeDimmer,
        device_profile=DeviceProfile.RF_DIMMER_WITH_VIRT_CHANNEL,
        custom_config=custom_config,
    )


def make_ip_fixed_color_light(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create fixed color light entities like HmIP-BSL."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpFixedColorLight,
        device_profile=DeviceProfile.IP_FIXED_COLOR_LIGHT,
        custom_config=custom_config,
    )


def make_ip_simple_fixed_color_light_wired(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create simple fixed color light entities like HmIPW-WRC6."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpFixedColorLight,
        device_profile=DeviceProfile.IP_SIMPLE_FIXED_COLOR_LIGHT_WIRED,
        custom_config=custom_config,
    )


def make_ip_rgbw_light(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create simple fixed color light entities like HmIP-RGBW."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpRGBWLight,
        device_profile=DeviceProfile.IP_RGBW_LIGHT,
        custom_config=custom_config,
    )


def make_ip_drg_dali_light(
    channel: hmd.HmChannel,
    custom_config: CustomConfig,
) -> None:
    """Create color light entities like HmIP-DRG-DALI."""
    hmed.make_custom_entity(
        channel=channel,
        entity_class=CeIpDrgDaliLight,
        device_profile=DeviceProfile.IP_DRG_DALI,
        custom_config=custom_config,
    )


# Case for device model is not relevant.
# HomeBrew (HB-) devices are always listed as HM-.
DEVICES: Mapping[str, CustomConfig | tuple[CustomConfig, ...]] = {
    "263 132": CustomConfig(make_ce_func=make_rf_dimmer),
    "263 133": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "263 134": CustomConfig(make_ce_func=make_rf_dimmer),
    "HBW-LC4-IN4-DR": CustomConfig(
        make_ce_func=make_rf_dimmer,
        channels=(
            5,
            6,
            7,
            8,
        ),
        extended=ExtendedConfig(
            additional_entities={
                1: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                2: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                3: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
                4: (
                    Parameter.PRESS_LONG,
                    Parameter.PRESS_SHORT,
                    Parameter.SENSOR,
                ),
            }
        ),
    ),
    "HBW-LC-RGBWW-IN6-DR": (
        CustomConfig(
            make_ce_func=make_rf_dimmer,
            channels=(7, 8, 9, 10, 11, 12),
            extended=ExtendedConfig(
                additional_entities={
                    (
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                    ): (
                        Parameter.PRESS_LONG,
                        Parameter.PRESS_SHORT,
                        Parameter.SENSOR,
                    )
                },
            ),
        ),
        CustomConfig(
            make_ce_func=make_rf_dimmer_color_fixed,
            channels=(13,),
            extended=ExtendedConfig(fixed_channels={15: {Field.COLOR: Parameter.COLOR}}),
        ),
        CustomConfig(
            make_ce_func=make_rf_dimmer_color_fixed,
            channels=(14,),
            extended=ExtendedConfig(fixed_channels={16: {Field.COLOR: Parameter.COLOR}}),
        ),
    ),
    "HM-DW-WM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4)),
    "HM-LC-AO-SM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-DW-WM": CustomConfig(make_ce_func=make_rf_dimmer_color_temp, channels=(1, 3, 5)),
    "HM-LC-Dim1L-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-Pl": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1L-Pl-2": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1L-Pl-3": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1PWM-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1PWM-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-CV": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-CV-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-DR": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3)),
    "HM-LC-Dim1T-FM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-FM-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-FM-LF": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1T-Pl": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1T-Pl-2": CustomConfig(make_ce_func=make_rf_dimmer),
    "HM-LC-Dim1T-Pl-3": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1TPBU-FM": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim1TPBU-FM-2": CustomConfig(make_ce_func=make_rf_dimmer_with_virt_channel),
    "HM-LC-Dim2L-CV": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2L-SM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2L-SM-2": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
    "HM-LC-Dim2T-SM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2)),
    "HM-LC-Dim2T-SM-2": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
    "HM-LC-RGBW-WM": CustomConfig(make_ce_func=make_rf_dimmer_color_effect),
    "HMW-LC-Dim1L-DR": CustomConfig(make_ce_func=make_rf_dimmer, channels=(3,)),
    "HSS-DX": CustomConfig(make_ce_func=make_rf_dimmer),
    "HmIP-DRG-DALI": CustomConfig(
        make_ce_func=make_ip_drg_dali_light, channels=tuple(range(1, 49))
    ),
    "HmIP-BDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(4,)),
    "HmIP-BSL": CustomConfig(make_ce_func=make_ip_fixed_color_light, channels=(8, 12)),
    "HmIP-DRDI3": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(5, 9, 13),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIP-FDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(2,)),
    "HmIP-PDT": CustomConfig(make_ce_func=make_ip_dimmer, channels=(3,)),
    "HmIP-RGBW": CustomConfig(make_ce_func=make_ip_rgbw_light),
    "HmIP-SCTH230": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(12,),
        extended=ExtendedConfig(
            additional_entities={
                1: (Parameter.CONCENTRATION,),
                4: (
                    Parameter.HUMIDITY,
                    Parameter.ACTUAL_TEMPERATURE,
                ),
            }
        ),
    ),
    "HmIPW-DRD3": CustomConfig(
        make_ce_func=make_ip_dimmer,
        channels=(2, 6, 10),
        extended=ExtendedConfig(
            additional_entities={
                0: (Parameter.ACTUAL_TEMPERATURE,),
            }
        ),
    ),
    "HmIPW-WRC6": CustomConfig(
        make_ce_func=make_ip_simple_fixed_color_light_wired, channels=(7, 8, 9, 10, 11, 12, 13)
    ),
    "OLIGO.smart.iq.HM": CustomConfig(make_ce_func=make_rf_dimmer, channels=(1, 2, 3, 4, 5, 6)),
}
hmed.ALL_DEVICES[HmPlatform.LIGHT] = DEVICES
