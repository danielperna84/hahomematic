"""Tests for select entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.generic.select import HmSelect
from hahomematic.platforms.hub.select import HmSysvarSelect

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_hmselect(factory: helper.Factory) -> None:
    """Test HmSelect."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    select: HmSelect = cast(
        HmSelect,
        central.get_generic_entity("VCU6354483:1", "WINDOW_STATE"),
    )
    assert select.usage == EntityUsage.NO_CREATE
    assert select.unit is None
    assert select.min == "CLOSED"
    assert select.max == "OPEN"
    assert select.values == ("CLOSED", "OPEN")
    assert select.value == "CLOSED"
    await select.send_value("OPEN")
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6354483:1",
        paramset_key="VALUES",
        parameter="WINDOW_STATE",
        value=1,
    )
    assert select.value == "OPEN"
    central.event(const.INTERFACE_ID, "VCU6354483:1", "WINDOW_STATE", 0)
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

    call_count = len(mock_client.method_calls)
    await select.send_value(1)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_hmsysvarselect(factory: helper.Factory) -> None:
    """Test HmSysvarSelect."""
    central, mock_client = await factory.get_default_central({}, add_sysvars=True)
    select: HmSysvarSelect = cast(HmSysvarSelect, central.get_sysvar_entity("sv_list_ext"))
    assert select.usage == EntityUsage.ENTITY
    assert select.unit is None
    assert select.min is None
    assert select.max is None
    assert select.values == ("v1", "v2", "v3")
    assert select.value == "v1"
    await select.send_variable("v2")
    assert mock_client.method_calls[-1] == call.set_system_variable(name="sv_list_ext", value=1)
    assert select.value == "v2"
    await select.send_variable(3)
    # do not write. value above max
    assert select.value == "v2"
