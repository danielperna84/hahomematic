"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import pytest

from hahomematic.caches.visibility import check_ignore_parameters_is_clean
from hahomematic.const import CallSource, EntityUsage
from hahomematic.platforms.custom.definition import (
    get_required_parameters,
    validate_entity_definition,
)
from hahomematic.platforms.custom.switch import CeSwitch
from hahomematic.platforms.generic.sensor import HmSensor
from hahomematic.platforms.generic.switch import HmSwitch

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

# pylint: disable=protected-access


def test_validate_entity_definition() -> None:
    """Test validate_entity_definition."""
    assert validate_entity_definition() is not None


@pytest.mark.asyncio
async def test_custom_entity_callback(factory: helper.Factory) -> None:
    """Test CeSwitch."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    switch: CeSwitch = cast(CeSwitch, helper.get_prepared_custom_entity(central, "VCU2128127", 4))
    assert switch.usage == EntityUsage.CE_PRIMARY

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(update_callback=device_updated_mock, custom_id="some_id")
    switch.register_remove_callback(remove_callback=device_removed_mock)
    assert switch.value is None
    assert (
        str(switch) == "address_path: switch/CentralTest-BidCos-RF/vcu2128127_4/, "
        "type: HmIP-BSM, name: HmIP-BSM_VCU2128127"
    )
    central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert factory.entity_event_mock.call_args_list[-1] == call(
        const.INTERFACE_ID, "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert factory.entity_event_mock.call_args_list[-1] == call(
        const.INTERFACE_ID, "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=[switch.device.device_address]
    )
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    switch.unregister_update_callback(update_callback=device_updated_mock, custom_id="some_id")
    switch.unregister_remove_callback(remove_callback=device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
async def test_generic_entity_callback(factory: helper.Factory) -> None:
    """Test CeSwitch."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(HmSwitch, central.get_generic_entity("VCU2128127:4", "STATE"))
    assert switch.usage == EntityUsage.NO_CREATE

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(update_callback=device_updated_mock, custom_id="some_id")
    switch.register_remove_callback(remove_callback=device_removed_mock)
    assert switch.value is None
    assert (
        str(switch) == "address_path: switch/CentralTest-BidCos-RF/vcu2128127_4_state/, "
        "type: HmIP-BSM, name: HmIP-BSM_VCU2128127 State ch4"
    )
    central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert factory.entity_event_mock.call_args_list[-1] == call(
        const.INTERFACE_ID, "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert factory.entity_event_mock.call_args_list[-1] == call(
        const.INTERFACE_ID, "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=[switch.device.device_address]
    )
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    switch.unregister_update_callback(update_callback=device_updated_mock, custom_id="some_id")
    switch.unregister_remove_callback(remove_callback=device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
async def test_load_custom_entity(factory: helper.Factory) -> None:
    """Test load custom_entity."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(HmSwitch, helper.get_prepared_custom_entity(central, "VCU2128127", 4))
    await switch.load_entity_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-2] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        call_source="manual_or_scheduled",
    )
    assert mock_client.method_calls[-1] == call.get_value(
        channel_address="VCU2128127:3",
        paramset_key="VALUES",
        parameter="STATE",
        call_source="manual_or_scheduled",
    )


@pytest.mark.asyncio
async def test_load_generic_entity(factory: helper.Factory) -> None:
    """Test load generic_entity."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(HmSwitch, central.get_generic_entity("VCU2128127:4", "STATE"))
    await switch.load_entity_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-1] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        call_source="manual_or_scheduled",
    )


@pytest.mark.asyncio
async def test_generic_wrapped_entity(factory: helper.Factory) -> None:
    """Test wrapped entity."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    wrapped_entity: HmSensor = cast(HmSensor, central.get_generic_entity("VCU3609622:1", "LEVEL"))
    assert wrapped_entity._platform == "number"
    assert wrapped_entity._is_forced_sensor is True
    assert wrapped_entity.platform == "sensor"
    assert wrapped_entity.usage == EntityUsage.ENTITY


def test_custom_required_entities() -> None:
    """Test required parameters from entity definitions."""
    required_parameters = get_required_parameters()
    assert len(required_parameters) == 75
    assert check_ignore_parameters_is_clean() is True
