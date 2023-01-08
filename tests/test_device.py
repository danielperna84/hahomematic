"""Tests for devices of hahomematic."""
from __future__ import annotations

import asyncio
from typing import cast

import const
import helper
from helper import get_device, get_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.text import HmText

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}


@pytest.mark.asyncio
async def test_device_general(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device availability."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU2128127")
    assert device.device_address == "VCU2128127"
    assert device.name == "HmIP-BSM_VCU2128127"
    assert str(device) == "address: VCU2128127, type: 8, name: HmIP-BSM_VCU2128127, entities: 23"
    assert device.device_type == "HmIP-BSM"
    assert device.interface == "BidCos-RF"
    assert device.interface_id == const.LOCAL_INTERFACE_ID
    assert device.has_custom_entity_definition is True
    assert len(device.custom_entities) == 3
    assert len(device.channels) == 10


@pytest.mark.asyncio
async def test_device_availability(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device availability."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU6354483")
    assert device.available is True
    for generic_entity in device.generic_entities.values():
        assert generic_entity.available is True
    for custom_entity in device.custom_entities.values():
        assert custom_entity.available is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:0", "UNREACH", 1)
    assert device.available is False
    for generic_entity in device.generic_entities.values():
        assert generic_entity.available is False
    for custom_entity in device.custom_entities.values():
        assert custom_entity.available is False

    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:0", "UNREACH", 0)
    assert device.available is True
    for generic_entity in device.generic_entities.values():
        assert generic_entity.available is True
    for custom_entity in device.custom_entities.values():
        assert custom_entity.available is True


@pytest.mark.asyncio
async def test_device_config_pending(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device availability."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU2128127")
    assert device._e_config_pending.value is False
    last_save = central.paramset_descriptions.last_save
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", True)
    assert device._e_config_pending.value is True
    assert last_save == central.paramset_descriptions.last_save
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", False)
    assert device._e_config_pending.value is False
    await asyncio.sleep(2)
    assert last_save != central.paramset_descriptions.last_save
