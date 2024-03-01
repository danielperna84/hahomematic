"""Tests for binary_sensor entities of hahomematic."""

from __future__ import annotations

from typing import cast

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.generic.binary_sensor import HmBinarySensor
from hahomematic.platforms.hub.binary_sensor import HmSysvarBinarySensor

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU5864966": "HmIP-SWDO-I.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_hmbinarysensor(factory: helper.Factory) -> None:
    """Test HmBinarySensor."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    binary_sensor: HmBinarySensor = cast(
        HmBinarySensor,
        central.get_generic_entity("VCU5864966:1", "STATE"),
    )
    assert binary_sensor.usage == EntityUsage.ENTITY
    assert binary_sensor.value is False
    assert binary_sensor.is_writeable is False
    assert binary_sensor.visible is True
    central.event(const.INTERFACE_ID, "VCU5864966:1", "STATE", 1)
    assert binary_sensor.value is True
    central.event(const.INTERFACE_ID, "VCU5864966:1", "STATE", 0)
    assert binary_sensor.value is False
    central.event(const.INTERFACE_ID, "VCU5864966:1", "STATE", None)
    assert binary_sensor.value is False

    call_count = len(mock_client.method_calls)
    await binary_sensor.send_value(True)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_hmsysvarbinarysensor(factory: helper.Factory) -> None:
    """Test HmSysvarBinarySensor."""
    central, _ = await factory.get_default_central({}, add_sysvars=True)
    binary_sensor: HmSysvarBinarySensor = cast(
        HmSysvarBinarySensor,
        central.get_sysvar_entity("sv_logic"),
    )
    assert binary_sensor.name == "sv_logic"
    assert binary_sensor.full_name == "CentralTest_sv_logic"
    assert binary_sensor.value is False
    assert binary_sensor.is_extended is False
    assert binary_sensor.data_type == "LOGIC"
    with pytest.raises(TypeError):
        binary_sensor.write_value(None)
    assert binary_sensor.value is False
