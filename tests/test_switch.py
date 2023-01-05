"""Tests for switch entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_hm_custom_entity, get_hm_generic_entity, get_hm_sysvar_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.switch import CeSwitch
from hahomematic.generic_platforms.switch import HmSwitch, HmSysvarSwitch

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
}


@pytest.mark.asyncio
async def test_ceswitch(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSwitch."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: CeSwitch = cast(
        CeSwitch, await get_hm_custom_entity(central, "VCU2128127", 4)
    )
    assert switch.usage == HmEntityUsage.CE_PRIMARY

    assert switch.value is None
    assert switch.channel_value is False
    await switch.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
    )
    assert switch.value is False
    await switch.turn_on(**{"on_time": 60})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=60.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.set_on_time_value(35.4)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=35.4,
    )


@pytest.mark.asyncio
async def test_hmswitch(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSwitch."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: HmSwitch = cast(
        HmSwitch, await get_hm_generic_entity(central, "VCU2128127:4", "STATE")
    )
    assert switch.usage == HmEntityUsage.ENTITY_NO_CREATE

    assert switch.value is None
    await switch.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
    )
    assert switch.value is False
    await switch.turn_on(**{"on_time": 60})
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=60.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.set_on_time_value(35.4)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=35.4,
    )


@pytest.mark.asyncio
async def test_hmsysvarswitch(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarSwitch."""
    central, mock_client = await central_local_factory.get_central({}, add_sysvars=True)
    assert central
    switch: HmSysvarSwitch = cast(
        HmSysvarSwitch, await get_hm_sysvar_entity(central, "sv_alarm_ext")
    )
    assert switch.usage == HmEntityUsage.ENTITY

    assert switch.value is False
    await switch.send_variable(True)
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_alarm_ext", value=True
    )
