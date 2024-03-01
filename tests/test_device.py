"""Tests for devices of hahomematic."""

from __future__ import annotations

import asyncio

import pytest

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_device_general(factory: helper.Factory) -> None:
    """Test device availability."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU2128127")
    assert device.device_address == "VCU2128127"
    assert device.name == "HmIP-BSM_VCU2128127"
    assert (
        str(device) == "address: VCU2128127, "
        "type: 8, "
        "name: HmIP-BSM_VCU2128127, "
        "generic_entities: 27, "
        "custom_entities: 3, "
        "events: 6"
    )
    assert device.device_type == "HmIP-BSM"
    assert device.interface == "BidCos-RF"
    assert device.interface_id == const.INTERFACE_ID
    assert device.has_custom_entity_definition is True
    assert len(device.custom_entities) == 3
    assert len(device.channels) == 11


@pytest.mark.asyncio
async def test_device_availability(factory: helper.Factory) -> None:
    """Test device availability."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU6354483")
    assert device.available is True
    for generic_entity in device.generic_entities:
        assert generic_entity.available is True
    for custom_entity in device.custom_entities:
        assert custom_entity.available is True

    central.event(const.INTERFACE_ID, "VCU6354483:0", "UNREACH", 1)
    assert device.available is False
    for generic_entity in device.generic_entities:
        assert generic_entity.available is False
    for custom_entity in device.custom_entities:
        assert custom_entity.available is False

    central.event(const.INTERFACE_ID, "VCU6354483:0", "UNREACH", 0)
    assert device.available is True
    for generic_entity in device.generic_entities:
        assert generic_entity.available is True
    for custom_entity in device.custom_entities:
        assert custom_entity.available is True


@pytest.mark.asyncio
async def test_device_config_pending(factory: helper.Factory) -> None:
    """Test device availability."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU2128127")
    assert device._e_config_pending.value is False
    last_save = central.paramset_descriptions.last_save
    central.event(const.INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", True)
    assert device._e_config_pending.value is True
    assert last_save == central.paramset_descriptions.last_save
    central.event(const.INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", False)
    assert device._e_config_pending.value is False
    await asyncio.sleep(2)
    assert last_save != central.paramset_descriptions.last_save
