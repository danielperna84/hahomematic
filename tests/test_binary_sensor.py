"""Tests for binary_sensor entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_hm_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.binary_sensor import HmBinarySensor

TEST_DEVICES: dict[str, str] = {
    "VCU5864966": "HmIP-SWDO-I.json",
}


@pytest.mark.asyncio
async def test_hmbinarysensor(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmBinarySensor."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    binary_sensor: HmBinarySensor = cast(
        HmBinarySensor, await get_hm_generic_entity(central, "VCU5864966:1", "STATE")
    )
    assert binary_sensor.usage == HmEntityUsage.ENTITY
    assert binary_sensor.value is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU5864966:1", "STATE", 1)
    assert binary_sensor.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU5864966:1", "STATE", 0)
    assert binary_sensor.value is False
