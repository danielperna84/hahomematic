"""Tests for light entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.light import (
    CeColorDimmer,
    CeColorDimmerEffect,
    CeColorTempDimmer,
    CeDimmer,
    CeIpFixedColorLight,
)

TEST_DEVICES: dict[str, str] = {
    "VCU1399816": "HmIP-BDT.json",
    "VCU3747418": "HM-LC-RGBW-WM.json",
    "VCU0000115": "HM-LC-DW-WM.json",
    "VCU3716619": "HmIP-BSL.json",
    "VCU0000098": "HM-DW-WM.json",
    "VCU4704397": "HmIPW-WRC6.json",
    "VCU0000122": "HM-LC-Dim1L-CV.json",
    "VCU9973336": "HBW-LC-RGBWW-IN6-DR.json",
}


@pytest.mark.asyncio
async def test_cedimmer(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeDimmer."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    light: CeDimmer = cast(CeDimmer, await helper.get_custom_entity(central, "VCU1399816", 4))
    assert light.usage == HmEntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color is None
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is False
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effect_list is None

    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(**{"brightness": 28})
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    assert light.is_on

    assert light.channel_brightness is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU1399816:3", "LEVEL", 0.4)
    assert light.channel_brightness == 102

    await light.turn_on(**{"on_time": 5.0, "ramp_time": 6.0})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4",
        paramset_key="VALUES",
        value={"LEVEL": 0.10980392156862745, "RAMP_TIME": 6.0, "ON_TIME": 5.0},
    )
    await light.turn_on(**{"on_time": 5.0})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1399816:4",
        paramset_key="VALUES",
        value={"ON_TIME": 5.0, "LEVEL": 0.10980392156862745},
    )

    await light.turn_off(**{"ramp_time": 6.0})
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

    await light.set_on_time_value(0.5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4", paramset_key="VALUES", parameter="ON_TIME", value=0.5
    )

    await light._set_ramp_time_value(5.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1399816:4", paramset_key="VALUES", parameter="RAMP_TIME", value=5.0
    )

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


async def test_cecolordimmer(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeColorDimmer."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    light: CeColorDimmer = cast(
        CeColorDimmer, await helper.get_custom_entity(central, "VCU9973336", 9)
    )
    assert light.usage == HmEntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None

    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(**{"brightness": 28})
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.10980392156862745,
    )
    assert light.brightness == 28
    await light.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9", paramset_key="VALUES", parameter="LEVEL", value=0.0
    )
    assert light.brightness == 0

    assert light.hs_color == (0.0, 0.0)
    await light.turn_on(**{"hs_color": (44.4, 69.3)})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=25
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (45.0, 100)

    await light.turn_on(**{"hs_color": (0, 50)})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=0
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 100.0)
    await light.turn_on(**{"hs_color": (0, 1)})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU9973336:15", paramset_key="VALUES", parameter="COLOR", value=200
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9973336:9", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 0.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU9973336:15", "COLOR", 201)
    assert light.hs_color == (0.0, 0.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU9973336:15", "COLOR", None)
    assert light.hs_color == (0.0, 0.0)

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_cecolordimmereffect(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeColorDimmerEffect."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    light: CeColorDimmerEffect = cast(
        CeColorDimmerEffect, await helper.get_custom_entity(central, "VCU3747418", 1)
    )
    assert light.usage == HmEntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is True
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effect_list == [
        "Off",
        "Slow color change",
        "Medium color change",
        "Fast color change",
        "Campfire",
        "Waterfall",
        "TV simulation",
    ]

    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(**{"brightness": 28})
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
    await light.turn_on(**{"hs_color": (44.4, 69.3)})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:2", paramset_key="VALUES", parameter="COLOR", value=25
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (45.0, 100)

    await light.turn_on(**{"hs_color": (0, 50)})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:2", paramset_key="VALUES", parameter="COLOR", value=0
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.hs_color == (0.0, 100.0)

    await light.turn_on(**{"effect": "Slow color change"})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU3747418:3", paramset_key="VALUES", parameter="PROGRAM", value=1
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3747418:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.effect == "Slow color change"

    central.event(const.LOCAL_INTERFACE_ID, "VCU3747418:2", "COLOR", 201)
    assert light.hs_color == (0.0, 0.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU3747418:2", "COLOR", None)
    assert light.hs_color == (0.0, 0.0)

    await light.turn_on()
    call_count = len(mock_client.method_calls)
    await light.turn_on()
    assert call_count == len(mock_client.method_calls)

    await light.turn_off()
    call_count = len(mock_client.method_calls)
    await light.turn_off()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_cecolortempdimmer(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeColorTempDimmer."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    light: CeColorTempDimmer = cast(
        CeColorTempDimmer, await helper.get_custom_entity(central, "VCU0000115", 1)
    )
    assert light.usage == HmEntityUsage.CE_PRIMARY
    assert light.color_temp == 500
    assert light.hs_color is None
    assert light.supports_brightness is True
    assert light.supports_color_temperature is True
    assert light.supports_effects is False
    assert light.supports_hs_color is False
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effect_list is None
    assert light.brightness == 0
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000115:1", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(**{"brightness": 28})
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
    await light.turn_on(**{"color_temp": 433})
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
async def test_ceipfixedcolorlight(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpFixedColorLight."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    light: CeIpFixedColorLight = cast(
        CeIpFixedColorLight, await helper.get_custom_entity(central, "VCU3716619", 8)
    )
    assert light.usage == HmEntityUsage.CE_PRIMARY
    assert light.color_temp is None
    assert light.hs_color == (0.0, 0.0)
    assert light.supports_brightness is True
    assert light.supports_color_temperature is False
    assert light.supports_effects is False
    assert light.supports_hs_color is True
    assert light.supports_transition is True
    assert light.effect is None
    assert light.effect_list is None
    assert light.brightness == 0
    assert light.is_on is False
    assert light.color_name == "BLACK"
    assert light.channel_color_name is None
    assert light.channel_brightness is None
    assert light.channel_hs_color is None
    await light.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3716619:8", paramset_key="VALUES", parameter="LEVEL", value=1.0
    )
    assert light.brightness == 255
    await light.turn_on(**{"brightness": 28})
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
    assert light.color_name == "BLACK"

    await light.turn_on(**{"hs_color": (350, 50)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 4, "LEVEL": 1.0}
    )
    assert light.color_name == "RED"

    await light.turn_on(**{"hs_color": (0.0, 0.0)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 7, "LEVEL": 1.0}
    )
    assert light.color_name == "WHITE"

    await light.turn_on(**{"hs_color": (60.0, 50.0)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 6, "LEVEL": 1.0}
    )
    assert light.color_name == "YELLOW"

    await light.turn_on(**{"hs_color": (120, 50)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 2, "LEVEL": 1.0}
    )
    assert light.color_name == "GREEN"

    await light.turn_on(**{"hs_color": (180, 50)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 3, "LEVEL": 1.0}
    )
    assert light.color_name == "TURQUOISE"

    await light.turn_on(**{"hs_color": (240, 50)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 1, "LEVEL": 1.0}
    )
    assert light.color_name == "BLUE"

    await light.turn_on(**{"hs_color": (300, 50)})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8", paramset_key="VALUES", value={"COLOR": 5, "LEVEL": 1.0}
    )
    assert light.color_name == "PURPLE"

    central.event(const.LOCAL_INTERFACE_ID, "VCU3716619:7", "LEVEL", 0.5)
    assert light.channel_brightness == 127

    central.event(const.LOCAL_INTERFACE_ID, "VCU3716619:7", "COLOR", 1)
    assert light.channel_hs_color == (240.0, 100.0)
    assert light.channel_color_name == "BLUE"

    await light.set_on_time_value(18)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_UNIT": 0, "DURATION_VALUE": 18},
    )

    await light.set_on_time_value(17000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_UNIT": 1, "DURATION_VALUE": 283},
    )

    await light.set_on_time_value(1000000)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"DURATION_UNIT": 2, "DURATION_VALUE": 277},
    )
    await light.turn_on(**{"ramp_time": 18})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"RAMP_TIME_UNIT": 0, "RAMP_TIME_VALUE": 18, "LEVEL": 1.0},
    )

    await light.turn_on(**{"ramp_time": 17000})
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3716619:8",
        paramset_key="VALUES",
        value={"RAMP_TIME_UNIT": 1, "RAMP_TIME_VALUE": 283, "LEVEL": 1.0},
    )

    await light.turn_on(**{"ramp_time": 1000000})
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
