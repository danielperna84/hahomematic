"""Test the HaHomematic central."""
from __future__ import annotations

from contextlib import suppress
from typing import cast
from unittest.mock import PropertyMock, patch, Mock

import const
import helper
from helper import get_device, get_generic_entity, load_device_description, get_mock
import pytest

from hahomematic.const import HmEntityUsage, HmPlatform
from hahomematic.generic_platforms.number import HmFloat
from hahomematic.generic_platforms.switch import HmSwitch
from hahomematic.client import Client, ClientLocal

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}


@pytest.mark.asyncio
async def test_central_basics(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central basics."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)

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
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU6354483")
    await device.export_device_definition()


@pytest.mark.asyncio
async def test_device_unignore(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device un ignore."""
    assert central_local_factory
    central1, mock_client1 = await central_local_factory.get_default_central(
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
        HmFloat, await get_generic_entity(central1, "VCU3609622:1", "LEVEL")
    )
    assert level1.usage == HmEntityUsage.ENTITY_NO_CREATE
    assert len(level1.device.generic_entities) == 22

    switch1: HmSwitch | None = None
    with suppress(AssertionError):
        switch1: HmSwitch = cast(
            HmSwitch,
            await get_generic_entity(central1, "VCU3609622:1", "VALVE_ADAPTION"),
        )
    assert switch1 is None

    central2, mock_client2 = await central_local_factory.get_default_central(
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
        HmFloat, await get_generic_entity(central2, "VCU3609622:1", "LEVEL")
    )
    assert level2.usage == HmEntityUsage.ENTITY
    assert len(level2.device.generic_entities) == 23
    switch2: HmSwitch = cast(
        HmSwitch, await get_generic_entity(central2, "VCU3609622:1", "VALVE_ADAPTION")
    )
    assert switch2.usage == HmEntityUsage.ENTITY


@pytest.mark.asyncio
async def test_all_parameters(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    parameters = central.paramset_descriptions.get_all_readable_parameters()
    assert parameters
    assert len(parameters) == 43


@pytest.mark.asyncio
async def test_entities_by_platform(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
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
    central, mock_client = await central_local_factory.get_default_central(
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
    central, mock_client = await central_local_factory.get_default_central(
        TEST_DEVICES, ignore_devices_on_create=["HmIP-BSM.json"]
    )
    assert len(central._devices) == 1
    assert len(central._entities) == 23
    assert (
        len(
            central.device_descriptions._raw_device_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 9
    )
    assert (
        len(
            central.paramset_descriptions._raw_paramset_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 8
    )
    dev_desc = load_device_description(central=central, filename="HmIP-BSM.json")
    await central.add_new_devices(const.LOCAL_INTERFACE_ID, dev_desc)
    assert len(central._devices) == 2
    assert len(central._entities) == 49
    assert (
        len(
            central.device_descriptions._raw_device_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 20
    )
    assert (
        len(
            central.paramset_descriptions._raw_paramset_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 18
    )


@pytest.mark.asyncio
async def test_delete_device(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    assert len(central._devices) == 2
    assert len(central._entities) == 49
    assert (
        len(
            central.device_descriptions._raw_device_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 20
    )
    assert (
        len(
            central.paramset_descriptions._raw_paramset_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 18
    )

    await central.delete_devices(const.LOCAL_INTERFACE_ID, ["VCU2128127"])
    assert len(central._devices) == 1
    assert len(central._entities) == 23
    assert (
        len(
            central.device_descriptions._raw_device_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 9
    )
    assert (
        len(
            central.paramset_descriptions._raw_paramset_descriptions_persistant_cache.get(
                const.LOCAL_INTERFACE_ID
            )
        )
        == 8
    )


@pytest.mark.asyncio
async def test_device_delete_virtual_remotes(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device un ignore."""
    assert central_local_factory
    central, mock_client = await central_local_factory.get_default_central(
        {
            "VCU4264293": "HmIP-RCV-50.json",
            "VCU0000057": "HM-RCV-50.json",
            "VCU0000001": "HMW-RCV-50.json",
        },
    )
    assert central.get_virtual_remotes()

    assert len(central._devices) == 3
    assert len(central._entities) == 350
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central.delete_devices(const.LOCAL_INTERFACE_ID, virtual_remotes)
    assert len(central._devices) == 0
    assert len(central._entities) == 0

    assert central.get_virtual_remotes() == []


@pytest.mark.asyncio
async def test_central_others(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central other methods."""
    assert central_local_factory
    central, client = await central_local_factory.get_unpatched_default_central({}, do_mock_client=False)
    mock_client = get_mock(instance=client, available=False)

    with patch("hahomematic.client.create_client", return_value=mock_client):
        await central.start()
        assert central.available is False
