"""Tests for sensor entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_hm_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.sensor import HmSensor

TEST_DEVICES: dict[str, str] = {
    "VCU7981740": "HmIP-SRH.json",
    "VCU3941846": "HMIP-PSM.json",
}


@pytest.mark.asyncio
async def test_hmsensor_psm(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSensor."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    sensor: HmSensor = cast(
        HmSensor, await get_hm_generic_entity(central, "VCU3941846:6", "VOLTAGE")
    )
    assert sensor.usage == HmEntityUsage.ENTITY
    assert sensor.unit == "V"
    assert sensor.value_list is None
    assert sensor.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:6", "VOLTAGE", 120)
    assert sensor.value == 120.0
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:6", "VOLTAGE", 234.00)
    assert sensor.value == 234.00


@pytest.mark.asyncio
async def test_hmsensor_srh(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSensor."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    sensor: HmSensor = cast(
        HmSensor, await get_hm_generic_entity(central, "VCU7981740:1", "STATE")
    )
    assert sensor.usage == HmEntityUsage.ENTITY
    assert sensor.unit is None
    assert sensor.value_list == ("CLOSED", "TILTED", "OPEN")
    assert sensor.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU7981740:1", "STATE", 0)
    assert sensor.value == "CLOSED"
    central.event(const.LOCAL_INTERFACE_ID, "VCU7981740:1", "STATE", 2)
    assert sensor.value == "OPEN"


# TODO: Add test for sysvar
