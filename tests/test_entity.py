"""Tests for switch entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, call

import const
import helper
import pytest

from hahomematic.const import HmCallSource, HmEntityUsage
from hahomematic.custom_platforms import get_required_parameters
from hahomematic.custom_platforms.switch import CeSwitch
from hahomematic.custom_platforms.entity_definition import validate_entity_definition
from hahomematic.generic_platforms.sensor import HmSensor
from hahomematic.generic_platforms.switch import HmSwitch
from hahomematic.parameter_visibility import check_ignore_parameters_is_clean

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

def test_validate_entity_definition() -> None:
    """Test validate_entity_definition."""
    assert validate_entity_definition() is not None

@pytest.mark.asyncio
async def test_custom_entity_callback(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSwitch."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    switch: CeSwitch = cast(CeSwitch, await helper.get_custom_entity(central, "VCU2128127", 4))
    assert switch.usage == HmEntityUsage.CE_PRIMARY

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(device_updated_mock)
    switch.register_remove_callback(device_removed_mock)
    assert switch.value is None
    assert str(switch) == "address: VCU2128127:4, type: HmIP-BSM, name: HmIP-BSM_VCU2128127"
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.LOCAL_INTERFACE_ID, addresses=[switch.device.device_address]
    )
    assert central_local_factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-Local", addresses=["VCU2128127"]
    )
    switch.unregister_update_callback(device_updated_mock)
    switch.unregister_remove_callback(device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
async def test_generic_entity_callback(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSwitch."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(
        HmSwitch, await helper.get_generic_entity(central, "VCU2128127:4", "STATE")
    )
    assert switch.usage == HmEntityUsage.ENTITY_NO_CREATE

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_update_callback(device_updated_mock)
    switch.register_remove_callback(device_removed_mock)
    assert switch.value is None
    assert (
        str(switch) == "address: VCU2128127:4, type: HmIP-BSM, name: HmIP-BSM_VCU2128127 State ch4"
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 1
    )
    assert switch.value is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert central_local_factory.entity_event_mock.call_args_list[-1] == call(
        const.LOCAL_INTERFACE_ID, "VCU2128127:4", "STATE", 0
    )
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.LOCAL_INTERFACE_ID, addresses=[switch.device.device_address]
    )
    assert central_local_factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-Local", addresses=["VCU2128127"]
    )
    switch.unregister_update_callback(device_updated_mock)
    switch.unregister_remove_callback(device_removed_mock)

    device_updated_mock.assert_called_with()
    device_removed_mock.assert_called_with()


@pytest.mark.asyncio
async def test_load_custom_entity(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test load custom_entity."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(HmSwitch, await helper.get_custom_entity(central, "VCU2128127", 4))
    await switch.load_entity_value(call_source=HmCallSource.MANUAL_OR_SCHEDULED)
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
async def test_load_generic_entity(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test load generic_entity."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    switch: HmSwitch = cast(
        HmSwitch, await helper.get_generic_entity(central, "VCU2128127:4", "STATE")
    )
    await switch.load_entity_value(call_source=HmCallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-1] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        call_source="manual_or_scheduled",
    )


@pytest.mark.asyncio
async def test_generic_wrapped_entity(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test wrapped entity."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    wrapped_entity: HmSensor = cast(
        HmSensor, await helper.get_wrapper_entity(central, "VCU3609622:1", "LEVEL")
    )
    assert wrapped_entity.usage == HmEntityUsage.ENTITY


def test_custom_required_entities() -> None:
    """Test required parameters from entity definitions."""
    required_parameters = get_required_parameters()
    assert len(required_parameters) == 64
    assert check_ignore_parameters_is_clean() is True
