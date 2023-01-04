"""Tests for action entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_generic_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.action import HmAction

TEST_DEVICES = {
    "VCU9724704": "HmIP-DLD.json",
}


@pytest.mark.asyncio
async def test_hmaction(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmAction."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    action: HmAction = cast(
        HmAction,
        await get_hm_generic_entity(central, "VCU9724704:1", "LOCK_TARGET_LEVEL"),
    )
    assert action.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert action.is_readable is False
    assert action.value is None
    assert action.value_list == ("LOCKED", "UNLOCKED", "OPEN")
    assert action.hmtype == "ENUM"
    assert action.send_value(2)
    assert action.value is None
    # TODO: check output with Mock
