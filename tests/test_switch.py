"""Tests for switch entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_hm_custom_entity, get_hm_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.switch import CeSwitch
from hahomematic.generic_platforms.switch import HmSwitch

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


# TODO: Add test for sysvar
