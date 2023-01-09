"""Test the HaHomematic central."""
from __future__ import annotations

import const
import helper
from helper import get_device, load_device_description
import pytest

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
    central, mock_client = await central_local_factory.get_central(
        TEST_DEVICES,
        un_ignore_list=[
            "LEVEL",
            "LEVEL@HmIP-eTRV-2:1:VALUES",
            "LEVEL@@HmIP-eTRV-2",
            "LEVEL@HmIP-eTRV-2",
            "LEVEL@HmIP-eTRV-2:1:MASTER",
            "VALUES:LEVEL",
            "HmIP-eTRV-2:1:MASTER"
        ],
    )
    # TODO: asserts


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
