"""Tests for switch entities of hahomematic."""
from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import MagicMock, call

import const
import helper
from helper import get_custom_entity, get_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.switch import CeSwitch
from hahomematic.generic_platforms.switch import HmSwitch

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
}


@pytest.mark.asyncio
async def test_custom_entity_callback(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSwitch."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: CeSwitch = cast(CeSwitch, await get_custom_entity(central, "VCU2128127", 4))
    assert switch.usage == HmEntityUsage.CE_PRIMARY

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(device_updated_mock)
    switch.register_remove_callback(device_removed_mock)
    assert switch.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        "CentralTest-Local", "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        "CentralTest-Local", "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        const.LOCAL_INTERFACE_ID, [switch.device.device_address]
    )
    assert central_local_factory.system_event_mock.call_args_list[-1] == call('deleteDevices', 'CentralTest-Local', ['VCU2128127'])
    switch.unregister_update_callback(device_updated_mock)
    switch.unregister_remove_callback(device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()

async def test_generic_entity_callback(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSwitch."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    switch: HmSwitch = cast(
        HmSwitch, await get_generic_entity(central, "VCU2128127:4", "STATE")
    )
    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(device_updated_mock)
    switch.register_remove_callback(device_removed_mock)
    assert switch.value is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        "CentralTest-Local", "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        "CentralTest-Local", "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        const.LOCAL_INTERFACE_ID, [switch.device.device_address]
    )
    assert central_local_factory.system_event_mock.call_args_list[-1] == call('deleteDevices', 'CentralTest-Local', [
        'VCU2128127'])

    switch.unregister_update_callback(device_updated_mock)
    switch.unregister_remove_callback(device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()
