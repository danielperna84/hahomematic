"""Tests for devices of hahomematic."""

from __future__ import annotations

import asyncio
from unittest.mock import Mock

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_device_general(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU2128127")
    assert device.address == "VCU2128127"
    assert device.name == "HmIP-BSM_VCU2128127"
    assert (
        str(device) == "address: VCU2128127, "
        "model: 8, "
        "name: HmIP-BSM_VCU2128127, "
        "generic_entities: 27, "
        "custom_entities: 3, "
        "events: 6"
    )
    assert device.model == "HmIP-BSM"
    assert device.interface == "BidCos-RF"
    assert device.interface_id == const.INTERFACE_ID
    assert device.has_custom_entity_definition is True
    assert len(device.custom_entities) == 3
    assert len(device.channels) == 11


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_device_availability(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU6354483")
    assert device.available is True
    for generic_entity in device.generic_entities:
        assert generic_entity.available is True
    for custom_entity in device.custom_entities:
        assert custom_entity.available is True

    await central.event(const.INTERFACE_ID, "VCU6354483:0", "UNREACH", 1)
    assert device.available is False
    for generic_entity in device.generic_entities:
        assert generic_entity.available is False
    for custom_entity in device.custom_entities:
        assert custom_entity.available is False

    await central.event(const.INTERFACE_ID, "VCU6354483:0", "UNREACH", 0)
    assert device.available is True
    for generic_entity in device.generic_entities:
        assert generic_entity.available is True
    for custom_entity in device.custom_entities:
        assert custom_entity.available is True


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_device_config_pending(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test device availability."""
    central, _, _ = central_client_factory
    device = central.get_device(address="VCU2128127")
    assert device._e_config_pending.value is False
    cache_hash = central.paramset_descriptions.cache_hash
    last_save_triggered = central.paramset_descriptions.last_save_triggered
    await central.event(const.INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", True)
    assert device._e_config_pending.value is True
    assert cache_hash == central.paramset_descriptions.cache_hash
    assert last_save_triggered == central.paramset_descriptions.last_save_triggered
    await central.event(const.INTERFACE_ID, "VCU2128127:0", "CONFIG_PENDING", False)
    assert device._e_config_pending.value is False
    await asyncio.sleep(2)
    # Save triggered, but data not changed
    assert cache_hash == central.paramset_descriptions.cache_hash
    assert last_save_triggered != central.paramset_descriptions.last_save_triggered
