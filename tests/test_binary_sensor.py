"""Tests for binary_sensor entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_generic_entity, get_sysvar_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.binary_sensor import (
    HmBinarySensor,
    HmSysvarBinarySensor,
)

TEST_DEVICES: dict[str, str] = {
    "VCU5864966": "HmIP-SWDO-I.json",
}


@pytest.mark.asyncio
async def test_hmbinarysensor(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmBinarySensor."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    binary_sensor: HmBinarySensor = cast(
        HmBinarySensor, await get_generic_entity(central, "VCU5864966:1", "STATE")
    )
    assert binary_sensor.usage == HmEntityUsage.ENTITY
    assert binary_sensor.value is False
    assert binary_sensor.is_writeable is False
    assert binary_sensor.visible is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU5864966:1", "STATE", 1)
    assert binary_sensor.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU5864966:1", "STATE", 0)
    assert binary_sensor.value is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU5864966:1", "STATE", None)
    assert binary_sensor.value is False


@pytest.mark.asyncio
async def test_hmsysvarbinarysensor(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarBinarySensor."""
    central, mock_client = await central_local_factory.get_central({}, add_sysvars=True)
    binary_sensor: HmSysvarBinarySensor = cast(
        HmSysvarBinarySensor,
        await get_sysvar_entity(central, "sv_logic"),
    )
    assert binary_sensor.name == "Sv_Logic"
    assert binary_sensor.full_name == "CentralTest_Sv_Logic"
    assert binary_sensor.value is False
    assert binary_sensor.is_extended is False
    assert binary_sensor.data_type == "LOGIC"
    with pytest.raises(ValueError):
        binary_sensor.update_value(None)
    assert binary_sensor.value is False
