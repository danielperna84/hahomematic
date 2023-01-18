"""Tests for select entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.select import HmSelect, HmSysvarSelect

TEST_DEVICES: dict[str, str] = {
    "VCU6354483": "HmIP-STHD.json",
}


@pytest.mark.asyncio
async def test_hmselect(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSelect."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    select: HmSelect = cast(
        HmSelect,
        await helper.get_generic_entity(central, "VCU6354483:1", "WINDOW_STATE"),
    )
    assert select.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert select.unit is None
    assert select.min == "CLOSED"
    assert select.max == "OPEN"
    assert select.value_list == ("CLOSED", "OPEN")
    assert select.value == "CLOSED"
    await select.send_value("OPEN")
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6354483:1",
        paramset_key="VALUES",
        parameter="WINDOW_STATE",
        value=1,
    )
    assert select.value == "OPEN"
    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:1", "WINDOW_STATE", 0)
    assert select.value == "CLOSED"

    await select.send_value(3)
    # do not write. value above max
    assert select.value == "CLOSED"

    await select.send_value(1)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6354483:1",
        paramset_key="VALUES",
        parameter="WINDOW_STATE",
        value=1,
    )
    # do not write. value above max
    assert select.value == "OPEN"


@pytest.mark.asyncio
async def test_hmsysvarselect(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarSelect."""
    central, mock_client = await central_local_factory.get_default_central(
        {}, add_sysvars=True
    )
    select: HmSysvarSelect = cast(
        HmSysvarSelect, await helper.get_sysvar_entity(central, "sv_list_ext")
    )
    assert select.usage == HmEntityUsage.ENTITY
    assert select.unit is None
    assert select.min is None
    assert select.max is None
    assert select.value_list == ("v1", "v2", "v3")
    assert select.value == "v1"
    await select.send_variable("v2")
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_list_ext", value=1
    )
    assert select.value == "v2"
    await select.send_variable(3)
    # do not write. value above max
    assert select.value == "v2"
