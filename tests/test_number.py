"""Tests for number entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_generic_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.number import HmFloat, HmInteger

TEST_DEVICES = {
    "VCU4984404": "HmIPW-STHD.json",
}


@pytest.mark.asyncio
async def test_hmfloat(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmFloat."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    efloat: HmFloat = cast(
        HmFloat,
        await get_hm_generic_entity(central, "VCU4984404:1", "TEMPERATURE_MAXIMUM"),
    )
    assert efloat.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert efloat.unit == "°C"
    assert efloat.value_list is None
    assert efloat.value is None
    await efloat.send_value(23.0)
    assert efloat.value == 23.0
    central.event(const.LOCAL_INTERFACE_ID, "VCU4984404:1", "TEMPERATURE_MAXIMUM", 20.5)
    assert efloat.value == 20.5


@pytest.mark.asyncio
async def test_hminteger(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmInteger."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    einteger: HmInteger = cast(
        HmInteger,
        await get_hm_generic_entity(central, "VCU4984404:1", "SET_POINT_MODE"),
    )
    assert einteger.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert einteger.unit is None
    assert einteger.min == 0
    assert einteger.max == 3
    assert einteger.value_list is None
    assert einteger.value is None
    await einteger.send_value(3)
    assert einteger.value == 3
    central.event(const.LOCAL_INTERFACE_ID, "VCU4984404:1", "SET_POINT_MODE", 2)
    assert einteger.value == 2
    await einteger.send_value(6)  # do not write. value above max
    assert einteger.value == 2


# TODO: Add test for sysvar
