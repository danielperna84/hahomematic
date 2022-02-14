"""Test the HaHomematic central."""
from conftest import (
    get_hm_custom_entity,
    get_hm_device,
    get_hm_generic_entity,
    get_value_from_generic_entity,
    send_device_value_to_ccu,
)
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.devices.climate import ATTR_TEMPERATURE, CeRfThermostat
from hahomematic.devices.lock import LOCK_TARGET_LEVEL_OPEN


@pytest.mark.asyncio
async def test_central(central, loop) -> None:
    """Test the central."""
    assert central
    assert central.instance_name == "ccu-dev"
    assert central.model == "PyDevCCU"
    assert central.get_client_by_interface_id("ccu-dev-hm").model == "PyDevCCU"
    assert central.get_client().model == "PyDevCCU"

    data = {}
    for device in central.hm_devices.values():
        if device.device_type not in data:
            data[device.device_type] = {}
        for entity in device.entities.values():
            if entity.parameter not in data[device.device_type]:
                data[device.device_type][entity.parameter] = f"{entity.hmtype}"

    custom_entities = []
    for device in central.hm_devices.values():
        custom_entities.extend(device.custom_entities.values())

    ce_channels = {}
    for custom_entity in custom_entities:
        if custom_entity.device_type not in ce_channels:
            ce_channels[custom_entity.device_type] = []
        ce_channels[custom_entity.device_type].append(custom_entity.channel_no)

    entity_types = {}
    for entity in central.hm_entities.values():
        if hasattr(entity, "hmtype"):
            if entity.hmtype not in entity_types:
                entity_types[entity.hmtype] = {}
            if type(entity).__name__ not in entity_types[entity.hmtype]:
                entity_types[entity.hmtype][type(entity).__name__] = []

            entity_types[entity.hmtype][type(entity).__name__].append(entity)

    parameters = []
    for entity in central.hm_entities.values():
        if hasattr(entity, "parameter"):
            if entity.parameter not in parameters:
                parameters.append(entity.parameter)

    units = set()
    for entity in central.hm_entities.values():
        if hasattr(entity, "_unit"):
            units.add(entity._unit)

    lowbats = set()
    for entity in central.hm_entities.values():
        if hasattr(entity, "parameter") and entity.parameter == "LOWBAT":
            lowbats.add(entity.device_type)
    lowbats_sorted = sorted(lowbats)
    print(lowbats_sorted)

    usage_types: dict[HmEntityUsage,int] = {}
    for entity in central.hm_entities.values():
        if hasattr(entity, "usage"):
            if entity.usage not in usage_types:
                usage_types[entity.usage] = 0
            counter = usage_types[entity.usage]
            usage_types[entity.usage] = counter + 1

    assert usage_types[HmEntityUsage.ENTITY_NO_CREATE] == 1831
    assert usage_types[HmEntityUsage.CE_PRIMARY] == 161
    assert usage_types[HmEntityUsage.ENTITY] == 2468
    assert usage_types[HmEntityUsage.CE_SENSOR] == 63
    assert usage_types[HmEntityUsage.CE_SECONDARY] == 126

    assert len(central.hm_devices) == 362
    assert len(central.hm_entities) == 4649
    assert len(data) == 362
    assert len(custom_entities) == 287
    assert len(ce_channels) == 99
    assert len(entity_types) == 6
    assert len(parameters) == 178


@pytest.mark.asyncio
async def test_device_set_data(central, pydev_ccu, loop) -> None:
    """Test callback."""
    assert central
    assert pydev_ccu
    old_value = await get_value_from_generic_entity(
        central_unit=central, address="VCU6354483:1", parameter="SET_POINT_TEMPERATURE"
    )
    assert old_value == 4.5
    send_device_value_to_ccu(pydev_ccu, "VCU6354483:1", "SET_POINT_TEMPERATURE", 19.0)
    new_value = await get_value_from_generic_entity(
        central, "VCU6354483:1", "SET_POINT_TEMPERATURE"
    )
    assert new_value == 19.0


@pytest.mark.asyncio
async def test_action_on_lock(central, pydev_ccu, loop) -> None:
    """Test callback."""
    assert central
    assert pydev_ccu
    lock = await get_hm_custom_entity(central_unit=central, address="VCU9724704", channel_no=1, do_load=True)
    assert lock
    assert lock.is_locked is False
    await lock.lock()
    assert lock


@pytest.mark.asyncio
async def test_device_export(central, pydev_ccu, loop) -> None:
    """Test device export."""
    assert central
    assert pydev_ccu
    hm_device = get_hm_device(central_unit=central, address="VCU6354483")
    assert hm_device
    await hm_device.export_device_definition()


@pytest.mark.asyncio
async def test_all_parameters(central, pydev_ccu, loop) -> None:
    """Test device export."""
    assert central
    assert pydev_ccu
    parameters = central.paramset_descriptions.get_all_parameters()
    assert parameters


@pytest.mark.asyncio
async def test_device_hm_heatgroup(central, pydev_ccu, loop) -> None:
    """Test callback."""
    assert central
    assert pydev_ccu
    entity = await get_hm_generic_entity(central, "INT0000001:1", "SET_TEMPERATURE")
    old_value = entity.value
    assert old_value is None

    custom_entity: CeRfThermostat = await get_hm_custom_entity(central, "INT0000001", 1)
    assert custom_entity.current_temperature is None
    kwargs = {ATTR_TEMPERATURE: 19.0}
    await custom_entity.set_temperature(**kwargs)

    new_value = await get_value_from_generic_entity(
        central, "INT0000001:1", "SET_TEMPERATURE"
    )
    assert new_value == 19.0
    assert custom_entity._e_setpoint.value == 19.0
    assert custom_entity.target_temperature == 19.0
