"""Tests for devices of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_hm_device, get_hm_generic_entity
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
    assert central_local_factory
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    hm_device = get_hm_device(central_unit=central, address="VCU2128127")
    assert hm_device
    assert hm_device.device_address == "VCU2128127"
    assert hm_device.name == "HmIP-BSM_VCU2128127"
    assert hm_device.device_type == "HmIP-BSM"
    assert hm_device.interface == "BidCos-RF"
    assert hm_device.interface_id == const.LOCAL_INTERFACE_ID
    assert hm_device.has_custom_entity_definition is True
    assert len(hm_device.custom_entities) == 3
    assert len(hm_device.channels) == 10


@pytest.mark.asyncio
async def test_device_availability(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device availability."""
    assert central_local_factory
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    hm_device = get_hm_device(central_unit=central, address="VCU6354483")
    assert hm_device
    assert hm_device.available is True
    for generic_entity in hm_device.generic_entities.values():
        assert generic_entity.available is True
    for custom_entity in hm_device.custom_entities.values():
        assert custom_entity.available is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:0", "UNREACH", 1)
    assert hm_device.available is False
    for generic_entity in hm_device.generic_entities.values():
        assert generic_entity.available is False
    for custom_entity in hm_device.custom_entities.values():
        assert custom_entity.available is False

    central.event(const.LOCAL_INTERFACE_ID, "VCU6354483:0", "UNREACH", 0)
    assert hm_device.available is True
    for generic_entity in hm_device.generic_entities.values():
        assert generic_entity.available is True
    for custom_entity in hm_device.custom_entities.values():
        assert custom_entity.available is True
