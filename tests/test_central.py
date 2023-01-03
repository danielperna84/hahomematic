"""Test the HaHomematic central."""
from __future__ import annotations

from conftest import (
    get_hm_custom_entity,
    get_hm_device,
    get_hm_generic_entity,
    get_value_from_generic_entity,
)
from const import LOCAL_INTERFACE_ID
import helper
import pytest

from hahomematic.custom_platforms.climate import CeRfThermostat


@pytest.mark.asyncio
async def test_device_set_data(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test callback."""
    assert central_local_factory
    central = await central_local_factory.get_central({"VCU6354483": "HmIP-STHD.json"})
    assert central
    old_value = await get_value_from_generic_entity(
        central_unit=central, address="VCU6354483:1", parameter="SET_POINT_TEMPERATURE"
    )
    assert old_value is None
    central.event(LOCAL_INTERFACE_ID, "VCU6354483:1", "SET_POINT_TEMPERATURE", 19.0)
    new_value = await get_value_from_generic_entity(
        central, "VCU6354483:1", "SET_POINT_TEMPERATURE"
    )
    assert new_value == 19.0


@pytest.mark.asyncio
async def test_action_on_lock(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test callback."""
    assert central_local_factory
    central = await central_local_factory.get_central({"VCU9724704": "HmIP-DLD.json"})
    assert central
    lock = await get_hm_custom_entity(
        central_unit=central, address="VCU9724704", channel_no=1, do_load=True
    )
    assert lock
    assert lock.is_locked is False
    await lock.lock()
    assert lock


@pytest.mark.asyncio
async def test_device_export(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    assert central_local_factory
    central = await central_local_factory.get_central({"VCU6354483": "HmIP-STHD.json"})
    assert central
    hm_device = get_hm_device(central_unit=central, address="VCU6354483")
    assert hm_device
    await hm_device.export_device_definition()


@pytest.mark.asyncio
async def test_all_parameters(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test device export."""
    assert central_local_factory
    central = await central_local_factory.get_central({"VCU6354483": "HmIP-STHD.json"})
    assert central
    parameters = central.paramset_descriptions.get_all_readable_parameters()
    assert parameters
    assert len(parameters) == 26


@pytest.mark.asyncio
async def test_device_hm_heatgroup(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test callback."""
    assert central_local_factory
    central = await central_local_factory.get_central({"INT0000001": "HM-CC-VG-1.json"})
    assert central
    entity = await get_hm_generic_entity(central, "INT0000001:1", "SET_TEMPERATURE")
    old_value = entity.value
    assert old_value is None

    custom_entity: CeRfThermostat = await get_hm_custom_entity(central, "INT0000001", 1)
    assert custom_entity.current_temperature is None
    await custom_entity.set_temperature(19.0)

    new_value = await get_value_from_generic_entity(
        central, "INT0000001:1", "SET_TEMPERATURE"
    )
    assert new_value == 19.0
    assert custom_entity._e_setpoint.value == 19.0
    assert custom_entity.target_temperature == 19.0
