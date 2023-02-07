"""Test the HaHomematic central."""
from __future__ import annotations

from contextlib import suppress
from typing import cast
from unittest.mock import call, patch

import const
import helper
import pytest

from hahomematic.const import (
    PARAMSET_KEY_VALUES,
    HmEntityUsage,
    HmInterfaceEventType,
    HmPlatform,
)
from hahomematic.exceptions import HaHomematicException, NoClients
from hahomematic.generic_platforms.number import HmFloat
from hahomematic.generic_platforms.switch import HmSwitch

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_central_basics(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central basics."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)

    assert central.central_url == "http://127.0.0.1"
    assert central.is_alive is True
    assert central.serial == "0"
    assert central.version == "0"
    assert await central.validate_config_and_get_serial() == "0815_4711"
    device = central.get_device("VCU2128127")
    assert device
    entities = central.get_readable_entities()
    assert entities


@pytest.mark.asyncio
async def test_device_export(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    assert central_local_factory
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    device = helper.get_device(central_unit=central, address="VCU6354483")
    await device.export_device_definition()


@pytest.mark.asyncio
async def test_identify_callback_ip(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    assert central_local_factory
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)

    assert await central._identify_callback_ip(port=54321) == "127.0.0.1"
    central.config.host = "no_host"
    assert await central._identify_callback_ip(port=54321) == "127.0.0.1"


@pytest.mark.asyncio
async def test_device_unignore(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device un ignore."""
    assert central_local_factory
    central1, _ = await central_local_factory.get_default_central(
        {"VCU3609622": "HmIP-eTRV-2.json"},
    )
    assert (
        central1.parameter_visibility.parameter_is_un_ignored(
            device_type="HmIP-eTRV-2",
            device_channel=1,
            paramset_key="VALUES",
            parameter="LEVEL",
        )
        is False
    )
    level1: HmFloat = cast(
        HmFloat, await helper.get_generic_entity(central1, "VCU3609622:1", "LEVEL")
    )
    assert level1.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert len(level1.device.generic_entities) == 22

    switch1: HmSwitch | None = None
    with suppress(AssertionError):
        switch1: HmSwitch = cast(
            HmSwitch,
            await helper.get_generic_entity(central1, "VCU3609622:1", "VALVE_ADAPTION"),
        )
    assert switch1 is None

    central2, _ = await central_local_factory.get_default_central(
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
            device_channel=1,
            paramset_key="VALUES",
            parameter="LEVEL",
        )
        is True
    )
    level2: HmFloat = cast(
        HmFloat, await helper.get_generic_entity(central2, "VCU3609622:1", "LEVEL")
    )
    assert level2.usage == HmEntityUsage.ENTITY
    assert len(level2.device.generic_entities) == 23
    switch2: HmSwitch = cast(
        HmSwitch,
        await helper.get_generic_entity(central2, "VCU3609622:1", "VALVE_ADAPTION"),
    )
    assert switch2.usage == HmEntityUsage.ENTITY


@pytest.mark.asyncio
async def test_all_parameters(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    parameters = central.paramset_descriptions.get_all_readable_parameters()
    assert parameters
    assert len(parameters) == 43


@pytest.mark.asyncio
async def test_entities_by_platform(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    ebp_sensor = central.get_entities_by_platform(platform=HmPlatform.SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 12
    ebp_sensor2 = central.get_entities_by_platform(
        platform=HmPlatform.SENSOR,
        existing_unique_ids=["vcu6354483_1_actual_temperature"],
    )
    assert ebp_sensor2
    assert len(ebp_sensor2) == 11


@pytest.mark.asyncio
async def test_hub_entities_by_platform(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, _ = await central_local_factory.get_default_central(
        {}, add_programs=True, add_sysvars=True
    )
    ebp_sensor = central.get_hub_entities_by_platform(platform=HmPlatform.HUB_SENSOR)
    assert ebp_sensor
    assert len(ebp_sensor) == 4
    ebp_sensor2 = central.get_hub_entities_by_platform(
        platform=HmPlatform.HUB_SENSOR,
        existing_unique_ids=["test1234_sysvar_sv-string"],
    )
    assert ebp_sensor2
    assert len(ebp_sensor2) == 3

    ebp_sensor3 = central.get_hub_entities_by_platform(platform=HmPlatform.HUB_BUTTON)
    assert ebp_sensor3
    assert len(ebp_sensor3) == 2
    ebp_sensor4 = central.get_hub_entities_by_platform(
        platform=HmPlatform.HUB_BUTTON, existing_unique_ids=["test1234_program_p-2"]
    )
    assert ebp_sensor4
    assert len(ebp_sensor4) == 1


@pytest.mark.asyncio
async def test_add_device(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, _ = await central_local_factory.get_default_central(
        TEST_DEVICES, ignore_devices_on_create=["HmIP-BSM.json"]
    )
    assert len(central._devices) == 1
    assert len(central._entities) == 23
    assert (
        len(central.device_descriptions._raw_device_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 9
    )
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 8
    )
    dev_desc = helper.load_device_description(central=central, filename="HmIP-BSM.json")
    await central.add_new_devices(
        interface_id=const.LOCAL_INTERFACE_ID, device_descriptions=dev_desc
    )
    assert len(central._devices) == 2
    assert len(central._entities) == 49
    assert (
        len(central.device_descriptions._raw_device_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 20
    )
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 18
    )
    await central.add_new_devices(interface_id="NOT_ANINTERFACE_ID", device_descriptions=dev_desc)
    assert len(central._devices) == 2


@pytest.mark.asyncio
async def test_delete_device(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    assert len(central._devices) == 2
    assert len(central._entities) == 49
    assert (
        len(central.device_descriptions._raw_device_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 20
    )
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 18
    )

    await central.delete_devices(interface_id=const.LOCAL_INTERFACE_ID, addresses=["VCU2128127"])
    assert len(central._devices) == 1
    assert len(central._entities) == 23
    assert (
        len(central.device_descriptions._raw_device_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 9
    )
    assert (
        len(central.paramset_descriptions._raw_paramset_descriptions.get(const.LOCAL_INTERFACE_ID))
        == 8
    )


@pytest.mark.asyncio
async def test_virtual_remote_delete(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device delete."""
    assert central_local_factory
    central, _ = await central_local_factory.get_default_central(
        {
            "VCU4264293": "HmIP-RCV-50.json",
            "VCU0000057": "HM-RCV-50.json",
            "VCU0000001": "HMW-RCV-50.json",
        },
    )
    assert len(central.get_virtual_remotes()) == 1

    assert central._get_virtual_remote("VCU4264293")

    await central.delete_device(
        interface_id=const.LOCAL_INTERFACE_ID, device_address="NOT_A_DEVICE_ID"
    )

    assert len(central._devices) == 3
    assert len(central._entities) == 350
    await central.delete_devices(
        interface_id=const.LOCAL_INTERFACE_ID, addresses=["VCU4264293", "VCU0000057"]
    )
    assert len(central._devices) == 1
    assert len(central._entities) == 100
    await central.delete_device(interface_id=const.LOCAL_INTERFACE_ID, device_address="VCU0000001")
    assert len(central._devices) == 0
    assert len(central._entities) == 0
    assert central.get_virtual_remotes() == []

    await central.delete_device(
        interface_id=const.LOCAL_INTERFACE_ID, device_address="NOT_A_DEVICE_ID"
    )


@pytest.mark.asyncio
async def test_central_not_alive(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central other methods."""
    assert central_local_factory
    central, client = await central_local_factory.get_unpatched_default_central(
        {}, do_mock_client=False
    )
    mock_client = helper.get_mock(instance=client, available=False)

    assert central.serial is None
    assert central.is_alive is True

    mock_client.is_callback_alive.return_value = False
    with patch("hahomematic.client.create_client", return_value=mock_client):
        await central.start()

    assert central.available is False
    assert central.serial == "0"
    assert central.is_alive is False


@pytest.mark.asyncio
async def test_central_callbacks(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central other methods."""
    assert central_local_factory
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    central.fire_interface_event(
        interface_id="SOME_ID",
        interface_event_type=HmInterfaceEventType.CALLBACK,
        available=False,
    )
    assert central_local_factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.interface",
        {"interface_id": "SOME_ID", "type": "callback", "value": False},
    )


@pytest.mark.asyncio
async def test_central_services(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central fetch sysvar and programs."""
    assert central_local_factory
    central, mock_client = await central_local_factory.get_default_central(
        TEST_DEVICES, add_programs=True, add_sysvars=True
    )

    await central.fetch_program_data()
    assert mock_client.method_calls[-1] == call.get_all_programs(include_internal=False)

    await central.fetch_sysvar_data()
    assert mock_client.method_calls[-1] == call.get_all_system_variables(include_internal=True)

    assert len(mock_client.method_calls) == 41
    await central.refresh_entity_data(paramset_key="MASTER")
    assert len(mock_client.method_calls) == 41
    await central.refresh_entity_data(paramset_key="VALUES")
    assert len(mock_client.method_calls) == 73

    await central.get_system_variable(name="SysVar_Name")
    assert mock_client.method_calls[-1] == call.get_system_variable("SysVar_Name")

    assert len(mock_client.method_calls) == 74
    await central.set_system_variable(name="sv_alarm", value=True)
    assert mock_client.method_calls[-1] == call.set_system_variable(name="sv_alarm", value=True)
    assert len(mock_client.method_calls) == 75
    await central.set_system_variable(name="SysVar_Name", value=True)
    assert len(mock_client.method_calls) == 75

    await central.set_install_mode(interface_id=const.LOCAL_INTERFACE_ID)
    assert mock_client.method_calls[-1] == call.set_install_mode(
        on=True, t=60, mode=1, device_address=None
    )
    assert len(mock_client.method_calls) == 76
    await central.set_install_mode(interface_id="NOT_A_VALID_INTERFACE_ID")
    assert len(mock_client.method_calls) == 76

    await central.get_client(interface_id=const.LOCAL_INTERFACE_ID).set_value(
        channel_address="123",
        paramset_key=PARAMSET_KEY_VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="123",
        paramset_key=PARAMSET_KEY_VALUES,
        parameter="LEVEL",
        value=1.0,
    )
    assert len(mock_client.method_calls) == 77

    with pytest.raises(HaHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").set_value(
            channel_address="123",
            paramset_key=PARAMSET_KEY_VALUES,
            parameter="LEVEL",
            value=1.0,
        )
    assert len(mock_client.method_calls) == 77

    await central.get_client(interface_id=const.LOCAL_INTERFACE_ID).put_paramset(
        address="123",
        paramset_key=PARAMSET_KEY_VALUES,
        value={"LEVEL": 1.0},
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="123", paramset_key="VALUES", value={"LEVEL": 1.0}
    )
    assert len(mock_client.method_calls) == 78
    with pytest.raises(HaHomematicException):
        await central.get_client(interface_id="NOT_A_VALID_INTERFACE_ID").put_paramset(
            address="123",
            paramset_key=PARAMSET_KEY_VALUES,
            value={"LEVEL": 1.0},
        )
    assert len(mock_client.method_calls) == 78

    assert (
        central.get_generic_entity(
            channel_address="VCU6354483:0", parameter="DUTY_CYCLE"
        ).parameter
        == "DUTY_CYCLE"
    )
    assert central.get_generic_entity(channel_address="VCU6354483", parameter="DUTY_CYCLE") is None


@pytest.mark.asyncio
async def test_central_direct(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central other methods."""
    assert central_local_factory
    central, client = await central_local_factory.get_unpatched_default_central(
        TEST_DEVICES, do_mock_client=False
    )
    mock_client = helper.get_mock(instance=client, available=False)

    assert central.serial is None
    assert central.is_alive is True

    with patch("hahomematic.client.create_client", return_value=mock_client):
        await central.start_direct()
    assert await central._create_clients() is False

    assert central.available is False
    assert central.serial == "0"
    assert len(central._devices) == 2
    assert len(central._entities) == 49
    await central.stop()


@pytest.mark.asyncio
async def test_central_without_interface_config(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central other methods."""
    assert central_local_factory
    central = await central_local_factory.get_raw_central(interface_config=None)
    assert central.has_clients is False

    with pytest.raises(NoClients):
        await central.validate_config_and_get_serial()

    with pytest.raises(HaHomematicException):
        central.get_client("NOT_A_VALID_INTERFACE_ID")

    with pytest.raises(Exception):
        await central._create_devices()

    await central.start_direct()
    assert central.has_clients is False

    assert central.available is True
    assert central.serial is None
    assert len(central._devices) == 0
    assert len(central._entities) == 0

    assert await central.get_system_variable(name="SysVar_Name") is None
    assert central._get_virtual_remote("VCU4264293") is None

    await central.stop()
