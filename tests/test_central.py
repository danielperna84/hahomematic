"""Test the HaHomematic central."""
from __future__ import annotations

from contextlib import suppress
from typing import cast

import const
import helper
from helper import get_device, get_generic_entity, load_device_description
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.number import HmFloat
from hahomematic.generic_platforms.switch import HmSwitch

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU6354483": "HmIP-STHD.json",
}


@pytest.mark.asyncio
async def test_central_basics(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test central basics."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)

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
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU6354483")
    await device.export_device_definition()


@pytest.mark.asyncio
async def test_device_unignore(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device un ignore."""
    assert central_local_factory
    central1, mock_client1 = await central_local_factory.get_central(
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

    central2, mock_client2 = await central_local_factory.get_central(
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
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    parameters = central.paramset_descriptions.get_all_readable_parameters()
    assert parameters
    assert len(parameters) == 43


@pytest.mark.asyncio
async def test_add_device(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    central, mock_client = await central_local_factory.get_central(
        TEST_DEVICES, ignore_device_on_create=["HmIP-BSM.json"]
    )
    assert len(central._devices) == 1
    assert len(central._entities) == 24
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
    assert len(central._entities) == 50
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
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert len(central._devices) == 2
    assert len(central._entities) == 50
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
    assert len(central._entities) == 24
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
    central, mock_client = await central_local_factory.get_central(
        {
            "VCU4264293": "HmIP-RCV-50.json",
            "VCU0000057": "HM-RCV-50.json",
            "VCU0000001": "HMW-RCV-50.json",
        },
    )
    assert len(central._devices) == 3
    assert len(central._entities) == 350
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central.delete_devices(const.LOCAL_INTERFACE_ID, virtual_remotes)
    assert len(central._devices) == 0
    assert len(central._entities) == 0
