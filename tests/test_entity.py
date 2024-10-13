"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock, Mock, call

import pytest

from hahomematic.caches.visibility import check_ignore_parameters_is_clean
from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import CallSource, EntityUsage
from hahomematic.platforms.custom import (
    CeSwitch,
    get_required_parameters,
    validate_entity_definition,
)
from hahomematic.platforms.generic import HmSensor, HmSwitch

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

# pylint: disable=protected-access


def test_validate_entity_definition() -> None:
    """Test validate_entity_definition."""
    assert validate_entity_definition() is not None


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
async def test_custom_entity_callback(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeSwitch."""
    central, _, factory = central_client_factory
    switch: CeSwitch = cast(CeSwitch, helper.get_prepared_custom_entity(central, "VCU2128127", 4))
    assert switch.usage == EntityUsage.CE_PRIMARY

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    unregister_entity_updated_callback = switch.register_entity_updated_callback(
        cb=device_updated_mock, custom_id="some_id"
    )
    unregister_device_removed_callback = switch.register_device_removed_callback(
        cb=device_removed_mock
    )
    assert switch.value is None
    assert (
        str(switch)
        == f"path: {central.config.base_path}CentralTest/VCU2128127/4/switch, name: HmIP-BSM_VCU2128127"
    )
    await central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert switch.value is True
    await central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=[switch.device.address]
    )
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    unregister_entity_updated_callback()
    unregister_device_removed_callback()

    device_updated_mock.assert_called_with(entity=switch)
    device_removed_mock.assert_called_with()


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
async def test_generic_entity_callback(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeSwitch."""
    central, _, factory = central_client_factory
    switch: HmSwitch = cast(HmSwitch, central.get_generic_entity("VCU2128127:4", "STATE"))
    assert switch.usage == EntityUsage.NO_CREATE

    device_updated_mock = MagicMock()
    device_removed_mock = MagicMock()

    switch.register_entity_updated_callback(cb=device_updated_mock, custom_id="some_id")
    switch.register_device_removed_callback(cb=device_removed_mock)
    assert switch.value is None
    assert (
        str(switch)
        == f"path: {central.config.base_path}CentralTest/VCU2128127/4/switch/state, name: HmIP-BSM_VCU2128127 State ch4"
    )
    await central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 1)
    assert switch.value is True
    await central.event(const.INTERFACE_ID, "VCU2128127:4", "STATE", 0)
    assert switch.value is False
    await central.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=[switch.device.address]
    )
    assert factory.system_event_mock.call_args_list[-1] == call(
        "deleteDevices", interface_id="CentralTest-BidCos-RF", addresses=["VCU2128127"]
    )
    switch._unregister_entity_updated_callback(cb=device_updated_mock, custom_id="some_id")
    switch._unregister_device_removed_callback(cb=device_removed_mock)

    device_updated_mock.assert_called_with(entity=switch)
    device_removed_mock.assert_called_with()


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
async def test_load_custom_entity(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test load custom_entity."""
    central, mock_client, _ = central_client_factory
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
async def test_load_generic_entity(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test load generic_entity."""
    central, mock_client, _ = central_client_factory
    switch: HmSwitch = cast(HmSwitch, central.get_generic_entity("VCU2128127:4", "STATE"))
    await switch.load_entity_value(call_source=CallSource.MANUAL_OR_SCHEDULED)
    assert mock_client.method_calls[-1] == call.get_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        call_source="manual_or_scheduled",
    )


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
async def test_generic_wrapped_entity(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test wrapped entity."""
    central, _, _ = central_client_factory
    wrapped_entity: HmSensor = cast(HmSensor, central.get_generic_entity("VCU3609622:1", "LEVEL"))
    assert wrapped_entity._platform == "number"
    assert wrapped_entity._is_forced_sensor is True
    assert wrapped_entity.platform == "sensor"
    assert wrapped_entity.usage == EntityUsage.ENTITY


def test_custom_required_entities() -> None:
    """Test required parameters from entity definitions."""
    required_parameters = get_required_parameters()
    assert len(required_parameters) == 79
    assert check_ignore_parameters_is_clean() is True
