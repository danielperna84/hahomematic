"""Tests for light entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage, ParamsetKey
from hahomematic.platforms.custom.light import (
    CeColorDimmer,
    CeColorDimmerEffect,
    CeColorTempDimmer,
    CeDimmer,
    CeIpFixedColorLight,
    CeIpRGBWLight,
    ColorBehaviour,
    FixedColor,
)

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU0000098": "HM-DW-WM.json",
    "VCU0000115": "HM-LC-DW-WM.json",
    "VCU0000122": "HM-LC-Dim1L-CV.json",
    "VCU1399816": "HmIP-BDT.json",
    "VCU3716619": "HmIP-BSL.json",
    "VCU3747418": "HM-LC-RGBW-WM.json",
    "VCU4704397": "HmIPW-WRC6.json",
    "VCU5629873": "HmIP-RGBW.json",
    "VCU9973336": "HBW-LC-RGBWW-IN6-DR.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_cedimmer(factory: helper.Factory) -> None:
    """Test CeDimmer."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeDimmer = cast(CeDimmer, helper.get_prepared_custom_entity(central, "VCU1399816", 4))
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color is None
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is False
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects is None

    assert light.brightness == 0
    assert light.brightness_pct == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    assert light.brightness_pct == 100
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    assert light.brightness_pct == 10
    assert light.is_on

    assert light.channel_brightness is None
    central.event(const.INTERFACE_ID, "VCU1399816:3", "LEVEL", 0.4)
    assert light.channel_brightness == 102

    await light.turn_on(on_time=5.0, ramp_time=6.0)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4",
        paramset_key="VALUES",
        value={"LEVEL": 0.10980392156862745, "RAMP_TIME": 6.0, "ON_TIME": 5.0},
    )
    await light.turn_on(on_time=5.0)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4",
        paramset_key="VALUES",
        value={"ON_TIME": 5.0, "LEVEL": 0.10980392156862745},
    )

    await light.turn_off(ramp_time=6.0)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4", paramset_key="VALUES", value={"RAMP_TIME": 6.0, "LEVEL": 0.0}
    )
    assert light.brightness == 0
    await light.turn_on()
    assert light.brightness == 255
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )

    await light.turn_off()
    light.set_on_time(0.5)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4", paramset_key="VALUES", value={"ON_TIME": 0.5, "LEVEL": 1.0}
    )

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_cecolordimmereffect(factory: helper.Factory) -> None:
    """Test CeColorDimmerEffect."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeColorDimmerEffect = cast(
        CeColorDimmerEffect, helper.get_prepared_custom_entity(central, "VCU3747418", 1)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is True
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects == (
        "Off",
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campfire",
        "Waterfall",
        "TV simulation",
    )

    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0

    assert light.hs_color == (0.0, 0.0)
    await light.turn_on(hs_color=(44.4, 69.3))
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:2", paramset_key="VALUES", parameter="COLOR", value=25
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (45.0, 100)

    await light.turn_on(hs_color=(0, 50))
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:2", paramset_key="VALUES", parameter="COLOR", value=0
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 100.0)

    await light.turn_on(effect="Slow color change")

    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:3", paramset_key="VALUES", parameter="PROGRAM", value=1
    )

    assert light.effect == "Slow color change"

    central.event(const.INTERFACE_ID, "VCU3747418:2", "COLOR", 201)
    assert light.hs_color == (0.0, 0.0)
    central.event(const.INTERFACE_ID, "VCU3747418:2", "COLOR", None)
    assert light.hs_color == (0.0, 0.0)

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)

    await light.turn_on(brightness=28, effect="Slow color change")
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:3", paramset_key="VALUES", parameter="PROGRAM", value=1
    )


@pytest.mark.asyncio
async def test_cecolortempdimmer(factory: helper.Factory) -> None:
    """Test CeColorTempDimmer."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeColorTempDimmer = cast(
        CeColorTempDimmer, helper.get_prepared_custom_entity(central, "VCU0000115", 1)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp == 500
    assert light.hs_color is None
    assert light.supports_brightness is True
    assert light.supports_color_temperature is True
    assert light.supports_effects is False
    assert light.supports_hs_color is False
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects is None
    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000115:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000115:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000115:1", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0

    assert light.color_temp == 500
    await light.turn_on(color_temp=433)
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU0000115:2",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.1930835734870317,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000115:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.color_temp == 433

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipfixedcolorlight(factory: helper.Factory) -> None:
    """Test CeIpFixedColorLight."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeIpFixedColorLight = cast(
        CeIpFixedColorLight, helper.get_prepared_custom_entity(central, "VCU3716619", 8)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects is None
    assert light.brightness == 0
    assert light.is_on is False
    assert light.color_name == FixedColor.BLACK
    assert light.channel_color_name is None
    assert light.channel_brightness is None
    assert light.channel_hs_color is None
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 7, "LEVEL": 1.0}
    )
    assert light.brightness == 255
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3716619:8",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3716619:8", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0
    assert light.color_name == FixedColor.WHITE

    await light.turn_on(hs_color=(350, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 4, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.RED

    await light.turn_on(hs_color=(0.0, 0.0))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 7, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.WHITE

    await light.turn_on(hs_color=(60.0, 50.0))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 6, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.YELLOW

    await light.turn_on(hs_color=(120, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 2, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.GREEN

    await light.turn_on(hs_color=(180, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 3, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.TURQUOISE

    await light.turn_on(hs_color=(240, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 1, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.BLUE

    await light.turn_on(hs_color=(300, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 5, "LEVEL": 1.0}
    )
    assert light.color_name == FixedColor.PURPLE

    central.event(const.INTERFACE_ID, "VCU3716619:7", "LEVEL", 0.5)
    assert light.channel_brightness == 127

    central.event(const.INTERFACE_ID, "VCU3716619:7", "COLOR", 1)
    assert light.channel_hs_color == (240.0, 100.0)
    assert light.channel_color_name == FixedColor.BLUE

    await light.turn_off()
    light.set_on_time(18)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_VALUE": 18, "LEVEL": 1.0},
    )

    await light.turn_off()
    light.set_on_time(17000)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_UNIT": 1, "DURATION_VALUE": 283, "LEVEL": 1.0},
    )

    await light.turn_off()
    light.set_on_time(1000000)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_UNIT": 2, "DURATION_VALUE": 277, "LEVEL": 1.0},
    )
    await light.turn_on(ramp_time=18)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"RAMP_TIME_VALUE": 18, "LEVEL": 1.0},
    )

    await light.turn_on(ramp_time=17000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"RAMP_TIME_UNIT": 1, "RAMP_TIME_VALUE": 283, "LEVEL": 1.0},
    )

    await light.turn_on(ramp_time=1000000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"RAMP_TIME_UNIT": 2, "RAMP_TIME_VALUE": 277, "LEVEL": 1.0},
    )

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipfixedcolorlightwired(factory: helper.Factory) -> None:
    """Test CeIpFixedColorLight."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeIpFixedColorLight = cast(
        CeIpFixedColorLight, helper.get_prepared_custom_entity(central, "VCU4704397", 8)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is True
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects == (
        ColorBehaviour.ON,
        "BLINKING_SLOW",
        "BLINKING_MIDDLE",
        "BLINKING_FAST",
        "FLASH_SLOW",
        "FLASH_MIDDLE",
        "FLASH_FAST",
        "BILLOW_SLOW",
        "BILLOW_MIDDLE",
        "BILLOW_FAST",
    )
    assert light.brightness == 0
    assert light.is_on is False
    assert light.color_name == FixedColor.BLACK
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 7, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.WHITE

    await light.turn_on(brightness=100)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "LEVEL": 0.39215686274509803},
    )
    assert light.brightness == 100
    assert light.color_name == FixedColor.WHITE
    assert light.effect == ColorBehaviour.ON

    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU4704397:8", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0
    assert light.color_name == FixedColor.WHITE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(350, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 4, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.RED
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(0.0, 0.0))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 7, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.WHITE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(60.0, 50.0))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 6, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.YELLOW
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(120, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 2, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.GREEN
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(180, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 3, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.TURQUOISE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(240, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 1, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.BLUE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(hs_color=(300, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "COLOR": 5, "LEVEL": 1.0},
    )
    assert light.brightness == 255
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == ColorBehaviour.ON

    await light.turn_off()
    assert light.brightness == 0
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(brightness=100)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "LEVEL": 0.39215686274509803},
    )
    assert light.brightness == 100
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(brightness=33)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 1, "LEVEL": 0.12941176470588237},
    )
    assert light.brightness == 33
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == ColorBehaviour.ON

    await light.turn_on(effect="FLASH_MIDDLE")
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "LEVEL": 0.12941176470588237},
    )
    assert light.brightness == 33
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == "FLASH_MIDDLE"

    await light.turn_on(brightness=66)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "LEVEL": 0.25882352941176473},
    )
    assert light.brightness == 66
    assert light.color_name == FixedColor.PURPLE
    assert light.effect == "FLASH_MIDDLE"

    await light.turn_off()

    light.set_on_time(18)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "DURATION_VALUE": 18, "LEVEL": 1.0},
    )

    await light.turn_off()
    light.set_on_time(17000)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "DURATION_UNIT": 1, "DURATION_VALUE": 283, "LEVEL": 1.0},
    )

    await light.turn_off()
    light.set_on_time(1000000)
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "DURATION_UNIT": 2, "DURATION_VALUE": 277, "LEVEL": 1.0},
    )
    await light.turn_on(ramp_time=18)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "RAMP_TIME_VALUE": 18, "LEVEL": 1.0},
    )

    await light.turn_on(ramp_time=17000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "RAMP_TIME_UNIT": 1, "RAMP_TIME_VALUE": 283, "LEVEL": 1.0},
    )

    await light.turn_on(ramp_time=1000000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "RAMP_TIME_UNIT": 2, "RAMP_TIME_VALUE": 277, "LEVEL": 1.0},
    )

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    await light.turn_on(effect="BLINKING_SLOW")
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8", paramset_key="VALUES", value={"COLOR_BEHAVIOUR": 2, "LEVEL": 1.0}
    )

    await light.turn_on(brightness=28)
    await light.turn_on(effect="FLASH_MIDDLE")
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU4704397:8",
        paramset_key="VALUES",
        value={"COLOR_BEHAVIOUR": 6, "LEVEL": 0.10980392156862745},
    )


async def test_ceiprgbwlight(factory: helper.Factory) -> None:
    """Test CeIpRGBWLight."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeIpRGBWLight = cast(
        CeIpRGBWLight, helper.get_prepared_custom_entity(central, "VCU5629873", 1)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color is None
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is True
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effects == (
        "NO_EFFECT",
        "EFFECT_01_END_CURRENT_PROFILE",
        "EFFECT_01_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_02_END_CURRENT_PROFILE",
        "EFFECT_02_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_03_END_CURRENT_PROFILE",
        "EFFECT_03_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_04_END_CURRENT_PROFILE",
        "EFFECT_04_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_05_END_CURRENT_PROFILE",
        "EFFECT_05_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_06_END_CURRENT_PROFILE",
        "EFFECT_06_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_07_END_CURRENT_PROFILE",
        "EFFECT_07_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_08_END_CURRENT_PROFILE",
        "EFFECT_08_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_09_END_CURRENT_PROFILE",
        "EFFECT_09_INTERRUPT_CURRENT_PROFILE",
        "EFFECT_10_END_CURRENT_PROFILE",
        "EFFECT_10_INTERRUPT_CURRENT_PROFILE",
    )

    assert light.brightness == 0

    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU5629873:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU5629873:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU5629873:1", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0

    assert light.color_temp is None
    await light.turn_on(color_temp=300)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU5629873:1",
        paramset_key="VALUES",
        value={"COLOR_TEMPERATURE": 3333, "LEVEL": 1.0},
    )
    assert light.color_temp == 300

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)

    assert light.hs_color is None
    await light.turn_on(hs_color=(44.4, 69.3))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU5629873:1",
        paramset_key="VALUES",
        value={"HUE": 44, "SATURATION": 0.693, "LEVEL": 1.0},
    )
    assert light.hs_color == (44, 69.3)

    await light.turn_on(hs_color=(0, 50))
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU5629873:1",
        paramset_key="VALUES",
        value={"HUE": 0, "SATURATION": 0.5, "LEVEL": 1.0},
    )
    assert light.hs_color == (0.0, 50.0)

    await light.turn_on(effect="EFFECT_01_END_CURRENT_PROFILE")
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU5629873:1", paramset_key="VALUES", value={"EFFECT": 1, "LEVEL": 1.0}
    )

    await light.turn_on(hs_color=(44, 66), ramp_time=5)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU5629873:1",
        paramset_key=ParamsetKey.VALUES,
        value={
            "HUE": 44,
            "SATURATION": 0.66,
            "DURATION_VALUE": 111600,
            "RAMP_TIME_VALUE": 5,
            "LEVEL": 1.0,
        },
    )


async def test_cecolordimmer(factory: helper.Factory) -> None:
    """Test CeColorDimmer."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    light: CeColorDimmer = cast(
        CeColorDimmer, helper.get_prepared_custom_entity(central, "VCU9973336", 13)
    )
    assert light.usage == EntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None

    assert light.brightness == 0
    assert light.brightness_pct == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(brightness=28)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0

    assert light.hs_color == (0.0, 0.0)
    await light.turn_on(hs_color=(44.4, 69.3))
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=25
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (45.0, 100)

    await light.turn_on(hs_color=(0, 50))
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=0
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 100.0)
    await light.turn_on(hs_color=(0, 1))
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=200
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:13", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 0.0)
    central.event(const.INTERFACE_ID, "VCU9973336:15", "COLOR", 201)
    assert light.hs_color == (0.0, 0.0)
    central.event(const.INTERFACE_ID, "VCU9973336:15", "COLOR", None)
    assert light.hs_color == (0.0, 0.0)

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)
