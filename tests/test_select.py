"""Tests for select entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_generic_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.select import HmSelect

TEST_DEVICES: dict[str, str] = {
    "VCU6354483": "HmIP-STHD.json",
}


@pytest.mark.asyncio
async def test_hmselect(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSelect."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    select: HmSelect = cast(
        HmSelect, await get_hm_generic_entity(central, "VCU6354483:1", "WINDOW_STATE")
    )
    assert select.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert select.unit is None
    assert select.min == "CLOSED"
    assert select.max == "OPEN"
    assert select.value_list == ("CLOSED", "OPEN")
    assert select.value == "CLOSED"
    await select.send_value("OPEN")
    assert select.value == "OPEN"
    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:1", "WINDOW_STATE", 0)
    assert select.value == "CLOSED"
    await select.send_value(3)  # do not write. value above max
    assert select.value == "CLOSED"


# TODO: Add test for sysvar