"""Tests for number entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.number import HmFloat, HmInteger, HmSysvarNumber

TEST_DEVICES: dict[str, str] = {
    "VCU4984404": "HmIPW-STHD.json",
    "VCU0000011": "HMW-LC-Bl1-DR.json",
}


@pytest.mark.asyncio
async def test_hmfloat(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmFloat."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    efloat: HmFloat = cast(
        HmFloat,
        await helper.get_generic_entity(central, "VCU0000011:3", "LEVEL"),
    )
    assert efloat.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert efloat.unit == "%"
    assert efloat.value_list is None
    assert efloat.value is None
    await efloat.send_value(0.3)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000011:3",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.3,
    )
    assert efloat.value == 0.3
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000011:3", "LEVEL", 0.5)
    assert efloat.value == 0.5
    # do not write. value above max
    await efloat.send_value(45.0)
    assert efloat.value == 0.5

    call_count = len(mock_client.method_calls)
    await efloat.send_value(45.0)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_hminteger(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmInteger."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    einteger: HmInteger = cast(
        HmInteger,
        await helper.get_generic_entity(central, "VCU4984404:1", "SET_POINT_MODE"),
    )
    assert einteger.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert einteger.unit is None
    assert einteger.min == 0
    assert einteger.max == 3
    assert einteger.value_list is None
    assert einteger.value is None
    await einteger.send_value(3)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU4984404:1",
        paramset_key="VALUES",
        parameter="SET_POINT_MODE",
        value=3,
    )
    assert einteger.value == 3
    central.event(const.LOCAL_INTERFACE_ID, "VCU4984404:1", "SET_POINT_MODE", 2)
    assert einteger.value == 2
    await einteger.send_value(6)
    assert mock_client.method_calls[-1] != call.set_value(
        channel_address="VCU4984404:1",
        paramset_key="VALUES",
        parameter="SET_POINT_MODE",
        value=6,
    )
    # do not write. value above max
    assert einteger.value == 2

    call_count = len(mock_client.method_calls)
    await einteger.send_value(6)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_hmsysvarnumber(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarNumber."""
    central, mock_client = await central_local_factory.get_default_central({}, add_sysvars=True)
    enumber: HmSysvarNumber = cast(
        HmSysvarNumber,
        await helper.get_sysvar_entity(central, "sv_float_ext"),
    )
    assert enumber.usage == HmEntityUsage.ENTITY
    assert enumber.unit == "°C"
    assert enumber.min == 5.0
    assert enumber.max == 30.0
    assert enumber.value_list is None
    assert enumber.value == 23.2

    await enumber.send_variable(23.0)
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_float_ext", value=23.0
    )
    assert enumber.value == 23.0

    await enumber.send_variable(35.0)
    # value over max won't change value
    assert enumber.value == 23.0
