"""Test the HaHomematic central."""
from __future__ import annotations

from contextlib import suppress
from datetime import datetime
from typing import Any, cast
from unittest.mock import call, patch

import pytest

from hahomematic.config import PING_PONG_MISMATCH_COUNT
from hahomematic.const import (
    DATETIME_FORMAT_MILLIS,
    EVENT_AVAILABLE,
    EntityUsage,
    EventType,
    HmPlatform,
    InterfaceEventType,
    Parameter,
    ParamsetKey,
)
from hahomematic.exceptions import HaHomematicException, NoClients
from hahomematic.platforms.generic.number import HmFloat, HmInteger
from hahomematic.platforms.generic.switch import HmSwitch

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_central_basics(factory: helper.Factory) -> None:
    """Test central basics."""
    central, client = await factory.get_default_central(TEST_DEVICES)
    assert central.central_url == "http://127.0.0.1"
    assert central.is_alive is True
    assert central.system_information.serial == "0815_4711"
    assert central.version == "0"
    system_information = await central.validate_config_and_get_system_information()
    assert system_information.serial == "0815_4711"
    device = central.get_device("VCU2128127")
    assert device
    entities = central.get_readable_generic_entities()
    assert entities


@pytest.mark.asyncio
async def test_device_get_entities(factory: helper.Factory) -> None:
    """Test central/device get_entities."""
    central, _ = await factory.get_default_central(
        TEST_DEVICES, add_sysvars=True, add_programs=True
    )
    entities = central.get_entities()
    assert entities

    entities_reg = central.get_entities(registered=True)
    assert entities_reg == ()


@pytest.mark.asyncio
async def test_device_export(factory: helper.Factory) -> None:
    """Test device export."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU6354483")
    await device.export_device_definition()


@pytest.mark.asyncio
async def test_identify_callback_ip(factory: helper.Factory) -> None:
    """Test identify_callback_ip."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    assert await central._identify_callback_ip(port=54321) == "127.0.0.1"
    central.config.host = "no_host"
    assert await central._identify_callback_ip(port=54321) == "127.0.0.1"


@pytest.mark.asyncio
async def test_device_unignore(factory: helper.Factory) -> None:
    """Test device un ignore."""
    central1, _ = await factory.get_default_central(
        {"VCU3609622": "HmIP-eTRV-2.json"}, un_ignore_list=["ACTIVE_PROFILE"]
    )
    assert (
        central1.parameter_visibility.parameter_is_un_ignored(
            device_type="HmIP-eTRV-2",
            channel_no=1,
            paramset_key="VALUES",
            parameter="ACTIVE_PROFILE",
        )
        is True
    )
    active_profile: HmInteger = cast(
        HmInteger, central1.get_generic_entity("VCU3609622:1", "ACTIVE_PROFILE")
    )
    assert active_profile.usage == EntityUsage.ENTITY
    assert len(active_profile.device.generic_entities) == 22

    switch1: HmSwitch | None = None
    with suppress(AssertionError):
        switch1: HmSwitch = cast(
            HmSwitch,
            central1.get_generic_entity("VCU3609622:1", "VALVE_ADAPTION"),
        )
    assert switch1 is None

    central2, _ = await factory.get_default_central(
        {"VCU3609622": "HmIP-eTRV-2.json"},
        un_ignore_list=[
            "LEVEL",  # parameter exists, but hidden
            "VALVE_ADAPTION",  # parameter is ignored
            "LEVEL@HmIP-eTRV-2:1:VALUES",  # input variant
            "LEVEL@@HmIP-eTRV-2",  # input variant
            "LEVEL@HmIP-eTRV-2",  # input variant
            "LEVEL@HmIP-eTRV-2:1:MASTER",  # input variant
            "VALUES:LEVEL",  # input variant
            "HmIP-eTRV-2:1:MASTER",  # input variant
        ],
    )
    assert (
        central2.parameter_visibility.parameter_is_un_ignored(
            device_type="HmIP-eTRV-2",
            channel_no=1,
            paramset_key="VALUES",
            parameter="LEVEL",
        )
        is True
    )
    level2: HmFloat = cast(HmFloat, central2.get_generic_entity("VCU3609622:1", "LEVEL"))
    assert level2.usage == EntityUsage.ENTITY
    assert len(level2.device.generic_entities) == 23
    switch2: HmSwitch = cast(
        HmSwitch,
        central2.get_generic_entity("VCU3609622:1", "VALVE_ADAPTION"),
    )
    assert switch2.usage == EntityUsage.ENTITY


@pytest.mark.asyncio
async def test_all_parameters(factory: helper.Factory) -> None:
    """Test all_parameters."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    parameters = central.paramset_descriptions.get_all_readable_parameters()
    assert parameters
    assert len(parameters) == 43


@pytest.mark.asyncio
async def test_entities_by_platform(factory: helper.Factory) -> None:
    """Test entities_by_platform."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    ebp_sensor = central.get_entities(platform=HmPlatform.SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 12

    def _device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""

    ebp_sensor[0].register_update_callback(update_callback=_device_changed, custom_id="some_id")
    ebp_sensor2 = central.get_entities(platform=HmPlatform.SENSOR, registered=False)
    assert ebp_sensor2
    assert len(ebp_sensor2) == 11


@pytest.mark.asyncio
async def test_hub_entities_by_platform(factory: helper.Factory) -> None:
    """Test hub_entities_by_platform."""
    central, _ = await factory.get_default_central({}, add_programs=True, add_sysvars=True)
    ebp_sensor = central.get_hub_entities(platform=HmPlatform.HUB_SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 4

    def _device_changed(self, *args: Any, **kwargs: Any) -> None:
        """Handle device state changes."""

    ebp_sensor[0].register_update_callback(update_callback=_device_changed, custom_id="some_id")
    ebp_sensor2 = central.get_hub_entities(
        platform=HmPlatform.HUB_SENSOR,
        registered=False,
    )
    assert ebp_sensor2
    assert len(ebp_sensor2) == 3

    ebp_sensor3 = central.get_hub_entities(platform=HmPlatform.HUB_BUTTON)
    assert ebp_sensor3
    assert len(ebp_sensor3) == 2
    ebp_sensor3[0].register_update_callback(update_callback=_device_changed, custom_id="some_id")
    ebp_sensor4 = central.get_hub_entities(platform=HmPlatform.HUB_BUTTON, registered=False)
    assert ebp_sensor4
    assert len(ebp_sensor4) == 1


@pytest.mark.asyncio
async def test_add_device(factory: helper.Factory) -> None:
    """Test add_device."""
    central, _ = await factory.get_default_central(
        TEST_DEVICES, ignore_devices_on_create=["HmIP-BSM.json"]
    )
    assert len(central._devices) == 1
    assert len(central.get_entities(exclude_no_create=False)) == 24
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 9
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 2
    )
    dev_desc = helper.load_device_description(central=central, filename="HmIP-BSM.json")
    await central.add_new_devices(interface_id=const.INTERFACE_ID, device_descriptions=dev_desc)
    assert len(central._devices) == 2
    assert len(central.get_entities(exclude_no_create=False)) == 55
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 20
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 11
    )
    await central.add_new_devices(interface_id="NOT_ANINTERFACE_ID", device_descriptions=dev_desc)
    assert len(central._devices) == 2


@pytest.mark.asyncio
async def test_delete_device(factory: helper.Factory) -> None:
    """Test device delete_device."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    assert len(central._devices) == 2
    assert len(central.get_entities(exclude_no_create=False)) == 55
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 20
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 11
    )

    await central.delete_devices(interface_id=const.INTERFACE_ID, addresses=["VCU2128127"])
    assert len(central._devices) == 1
    assert len(central.get_entities(exclude_no_create=False)) == 24
    assert len(central.device_descriptions._raw_device_descriptions.get(const.INTERFACE_ID)) == 9
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.INTERFACE_ID)) == 2
    )


@pytest.mark.asyncio
async def test_virtual_remote_delete(factory: helper.Factory) -> None:
    """Test device delete."""
    central, _ = await factory.get_default_central(
        {
            "VCU4264293": "HmIP-RCV-50.json",
            "VCU0000057": "HM-RCV-50.json",
            "VCU0000001": "HMW-RCV-50.json",
        },
    )
    assert len(central.get_virtual_remotes()) == 1

    assert central._get_virtual_remote("VCU0000057")

    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="NOT_A_DEVICE_ID")

    assert len(central._devices) == 3
    assert len(central.get_entities()) == 350
    await central.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=["VCU4264293", "VCU0000057"]
    )
    assert len(central._devices) == 1
    assert len(central.get_entities()) == 100
    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="VCU0000001")
    assert len(central._devices) == 0
    assert len(central.get_entities()) == 0
    assert central.get_virtual_remotes() == ()

    await central.delete_device(interface_id=const.INTERFACE_ID, device_address="NOT_A_DEVICE_ID")


@pytest.mark.asyncio
async def test_central_not_alive(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, client = await factory.get_unpatched_default_central({}, do_mock_client=False)
    mock_client = helper.get_mock(instance=client, available=False)

    assert central.system_information.serial is None
    assert central.is_alive is True

    mock_client.is_callback_alive.return_value = False
    with patch("hahomematic.client.create_client", return_value=mock_client):
        await central.start()

    assert central.available is False
    assert central.system_information.serial == "0815_4711"
    assert central.is_alive is False


@pytest.mark.asyncio
async def test_central_callbacks(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    central.fire_interface_event(
        interface_id="SOME_ID",
        interface_event_type=InterfaceEventType.CALLBACK,
        data={EVENT_AVAILABLE: False},
    )
    assert factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.interface",
        {
            "interface_id": "SOME_ID",
            "type": "callback",
            "data": {EVENT_AVAILABLE: False},
        },
    )


@pytest.mark.asyncio
async def test_central_services(factory: helper.Factory) -> None:
    """Test central fetch sysvar and programs."""
    central, mock_client = await factory.get_default_central(
        TEST_DEVICES, add_programs=True, add_sysvars=True
    )
    await central.fetch_program_data()
    assert mock_client.method_calls[-1] == call.get_all_programs(include_internal=False)

    await central.fetch_sysvar_data()
    assert mock_client.method_calls[-1] == call.get_all_system_variables(include_internal=True)

    assert len(mock_client.method_calls) == 37
    await central.load_and_refresh_entity_data(paramset_key=ParamsetKey.MASTER)
    assert len(mock_client.method_calls) == 37
    await central.load_and_refresh_entity_data(paramset_key=ParamsetKey.VALUES)
    assert len(mock_client.method_calls) == 54

    await central.get_system_variable(name="SysVar_Name")
    assert mock_client.method_calls[-1] == call.get_system_variable("SysVar_Name")

    assert len(mock_client.method_calls) == 55
    await central.set_system_variable(name="sv_alarm", value=True)
    assert mock_client.method_calls[-1] == call.set_system_variable(name="sv_alarm", value=True)
    assert len(mock_client.method_calls) == 56
    await central.set_system_variable(name="SysVar_Name", value=True)
    assert len(mock_client.method_calls) == 56

    await central.set_install_mode(interface_id=const.INTERFACE_ID)
    assert mock_client.method_calls[-1] == call.set_install_mode(
        on=True, t=60, mode=1, device_address=None
    )
    assert len(mock_client.method_calls) == 57
    await central.set_install_mode(interface_id="NOT_A_VALID_INTERFACE_ID")
    assert len(mock_client.method_calls) == 57

    await central.get_client(interface_id=const.INTERFACE_ID).set_value(
        channel_address="123",
        paramset_key=ParamsetKey.VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="123",
        paramset_key=ParamsetKey.VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert len(mock_client.method_calls) == 58

    with pytest.raises(HaHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").set_value(
            channel_address="123",
            paramset_key=ParamsetKey.VALUES,
            parameter="LEVEL",
            value=1.0,
        )
    assert len(mock_client.method_calls) == 58

    await central.get_client(interface_id=const.INTERFACE_ID).put_paramset(
        address="123",
        paramset_key=ParamsetKey.VALUES,
        value={"LEVEL": 1.0},
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="123", paramset_key="VALUES", value={"LEVEL": 1.0}
    )
    assert len(mock_client.method_calls) == 59
    with pytest.raises(HaHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").put_paramset(
            address="123",
            paramset_key=ParamsetKey.VALUES,
            value={"LEVEL": 1.0},
        )
    assert len(mock_client.method_calls) == 59

    assert (
        central.get_generic_entity(
            channel_address="VCU6354483:0", parameter="DUTY_CYCLE"
        ).parameter
        == "DUTY_CYCLE"
    )
    assert central.get_generic_entity(channel_address="VCU6354483", parameter="DUTY_CYCLE") is None


@pytest.mark.asyncio
async def test_central_direct(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, client = await factory.get_unpatched_default_central(
        TEST_DEVICES, do_mock_client=False
    )
    mock_client = helper.get_mock(instance=client, available=False)

    assert central.system_information.serial is None
    assert central.is_alive is True

    with patch("hahomematic.client.create_client", return_value=mock_client):
        await central.start()
    assert await central._create_clients() is False

    assert central.available is False
    assert central.system_information.serial == "0815_4711"
    assert len(central._devices) == 2
    assert len(central.get_entities(exclude_no_create=False)) == 55
    await central.stop()


@pytest.mark.asyncio
async def test_central_without_interface_config(factory: helper.Factory) -> None:
    """Test central other methods."""
    central = await factory.get_raw_central(interface_config=None)
    assert central.has_clients is False

    with pytest.raises(NoClients):
        await central.validate_config_and_get_system_information()

    with pytest.raises(HaHomematicException):
        central.get_client("NOT_A_VALID_INTERFACE_ID")

    with pytest.raises(Exception):
        await central._create_devices()

    await central.start()
    assert central.has_clients is False

    assert central.available is True
    assert central.system_information.serial is None
    assert len(central._devices) == 0
    assert len(central.get_entities()) == 0

    assert await central.get_system_variable(name="SysVar_Name") is None
    assert central._get_virtual_remote("VCU4264293") is None

    await central.stop()


@pytest.mark.asyncio
async def test_ping_pong(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, client = await factory.get_default_central(TEST_DEVICES, do_mock_client=False)
    interface_id = client.interface_id
    await client.check_connection_availability(handle_ping_pong=True)
    assert client.ping_pong_cache.pending_pong_count == 1
    for ts_stored in list(client.ping_pong_cache._pending_pongs):
        central.event(
            interface_id,
            "",
            Parameter.PONG,
            f"{interface_id}#{ts_stored.strftime(DATETIME_FORMAT_MILLIS)}",
        )
    assert client.ping_pong_cache.pending_pong_count == 0


@pytest.mark.asyncio
async def test_pending_pong_failure(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, client = await factory.get_default_central(TEST_DEVICES, do_mock_client=False)
    count = 0
    max_count = PING_PONG_MISMATCH_COUNT + 1
    while count < max_count:
        await client.check_connection_availability(handle_ping_pong=True)
        count += 1
    assert client.ping_pong_cache.pending_pong_count == max_count
    assert factory.ha_event_mock.mock_calls[-1] == call(
        EventType.INTERFACE,
        {
            "data": {
                "instance_name": "CentralTest",
                "pong_mismatch_count": 16,
            },
            "interface_id": "CentralTest-BidCos-RF",
            "type": InterfaceEventType.PENDING_PONG,
        },
    )
    assert len(factory.ha_event_mock.mock_calls) == 9


@pytest.mark.asyncio
async def test_unknown_pong_failure(factory: helper.Factory) -> None:
    """Test central other methods."""
    central, client = await factory.get_default_central(TEST_DEVICES, do_mock_client=False)
    interface_id = client.interface_id
    count = 0
    max_count = PING_PONG_MISMATCH_COUNT + 1
    while count < max_count:
        central.event(
            interface_id,
            "",
            Parameter.PONG,
            f"{interface_id}#{datetime.now().strftime(DATETIME_FORMAT_MILLIS)}",
        )
        count += 1

    assert client.ping_pong_cache.unknown_pong_count == 16


@pytest.mark.asyncio
async def test_central_caches(factory: helper.Factory) -> None:
    """Test central cache."""
    central, client = await factory.get_default_central(TEST_DEVICES)
    assert len(central.device_descriptions._raw_device_descriptions[client.interface_id]) == 20
    assert len(central.paramset_descriptions._raw_paramset_descriptions[client.interface_id]) == 11
    await central.clear_caches()
    assert central.device_descriptions._raw_device_descriptions.get(client.interface_id) is None
    assert (
        central.paramset_descriptions._raw_paramset_descriptions.get(client.interface_id) is None
    )


@pytest.mark.asyncio
async def test_central_getter(factory: helper.Factory) -> None:
    """Test central getter."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    assert central.get_device("123") is None
    assert central.get_custom_entity("123", 1) is None
    assert central.get_generic_entity("123", 1) is None
    assert central.get_event("123", 1) is None
    assert central.get_program_button("123") is None
    assert central.get_sysvar_entity("123") is None
