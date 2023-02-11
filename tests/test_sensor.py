"""Tests for sensor entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.hub.sensor import HmSysvarSensor

TEST_DEVICES: dict[str, str] = {
    "VCU7981740": "HmIP-SRH.json",
    "VCU3941846": "HMIP-PSM.json",
    "VCU8205532": "HmIP-SCTH230.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_hmsensor_psm(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSensor."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    sensor: HmSensor = cast(
        HmSensor, await helper.get_generic_entity(central, "VCU3941846:6", "VOLTAGE")
    )
    assert sensor.usage == HmEntityUsage.ENTITY
    assert sensor.unit == "V"
    assert sensor.value_list is None
    assert sensor.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:6", "VOLTAGE", 120)
    assert sensor.value == 120.0
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:6", "VOLTAGE", 234.00)
    assert sensor.value == 234.00

    sensor2: HmSensor = cast(
        HmSensor,
        await helper.get_generic_entity(central, "VCU3941846:0", "RSSI_DEVICE"),
    )
    assert sensor2.usage == HmEntityUsage.ENTITY
    assert sensor2.unit == "dBm"
    assert sensor2.value_list is None
    assert sensor2.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:0", "RSSI_DEVICE", 24)
    assert sensor2.value == -24
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:0", "RSSI_DEVICE", -40)
    assert sensor2.value == -40
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:0", "RSSI_DEVICE", -160)
    assert sensor2.value == -96
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:0", "RSSI_DEVICE", 160)
    assert sensor2.value == -96
    central.event(const.LOCAL_INTERFACE_ID, "VCU3941846:0", "RSSI_DEVICE", 400)
    assert sensor2.value is None

    sensor3: HmSensor = cast(
        HmSensor,
        await helper.get_generic_entity(central, "VCU8205532:1", "CONCENTRATION"),
    )
    assert sensor3.usage == HmEntityUsage.ENTITY
    assert sensor3.unit == "ppm"
    assert sensor3.value_list is None
    assert sensor3.value is None


@pytest.mark.asyncio
async def test_hmsensor_srh(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSensor."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    sensor: HmSensor = cast(
        HmSensor, await helper.get_generic_entity(central, "VCU7981740:1", "STATE")
    )
    assert sensor.usage == HmEntityUsage.ENTITY
    assert sensor.unit is None
    assert sensor.value_list == ("CLOSED", "TILTED", "OPEN")
    assert sensor.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU7981740:1", "STATE", 0)
    assert sensor.value == "CLOSED"
    central.event(const.LOCAL_INTERFACE_ID, "VCU7981740:1", "STATE", 2)
    assert sensor.value == "OPEN"


@pytest.mark.asyncio
async def test_hmsysvarsensor(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarSensor."""
    central, _ = await central_local_factory.get_default_central({}, add_sysvars=True)
    sensor: HmSysvarSensor = cast(
        HmSysvarSensor, await helper.get_sysvar_entity(central, "sv_list")
    )
    assert sensor.usage == HmEntityUsage.ENTITY
    assert sensor.available is True
    assert sensor.unit is None
    assert sensor.value_list == ("v1", "v2", "v3")
    assert sensor.value == "v1"

    sensor2: HmSysvarSensor = cast(
        HmSysvarSensor, await helper.get_sysvar_entity(central, "sv_float")
    )
    assert sensor2.usage == HmEntityUsage.ENTITY
    assert sensor2.unit is None
    assert sensor2.value_list is None
    assert sensor2.value == 23.2
