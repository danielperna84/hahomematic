"""Tests for switch entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_custom_entity, get_hm_generic_entity
import const
import helper
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
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: CeSwitch = cast(
        CeSwitch, await get_hm_custom_entity(central, "VCU2128127", 4)
    )
    assert switch.usage == HmEntityUsage.CE_PRIMARY

    assert switch.value is None
    await switch.turn_on()
    assert switch.value is True
    await switch.turn_off()
    assert switch.value is False


@pytest.mark.asyncio
async def test_hmswitch(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSwitch."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: HmSwitch = cast(
        HmSwitch, await get_hm_generic_entity(central, "VCU2128127:4", "STATE")
    )
    assert switch.usage == HmEntityUsage.ENTITY_NO_CREATE

    assert switch.value is None
    await switch.turn_on()
    assert switch.value is True
    await switch.turn_off()
    assert switch.value is False


# TODO: Add test for sysvar
