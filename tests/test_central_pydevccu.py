"""Test the HaHomematic central."""
from __future__ import annotations

import json
import os

import const
import pytest

from hahomematic.const import DEFAULT_ENCODING, HmEntityUsage
from hahomematic.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_value_property,
)


@pytest.mark.asyncio
async def test_central(central_pydevccu) -> None:
    """Test the central."""
    assert central_pydevccu
    assert central_pydevccu.name == const.CENTRAL_NAME
    assert central_pydevccu.model == "PyDevCCU"
    assert central_pydevccu.get_client(const.PYDEVCCU_INTERFACE_ID).model == "PyDevCCU"
    assert central_pydevccu.get_primary_client().model == "PyDevCCU"

    data = {}
    for device in central_pydevccu.devices:
        if device.device_type not in data:
            data[device.device_type] = {}
        for entity in device.generic_entities.values():
            if entity.parameter not in data[device.device_type]:
                data[device.device_type][entity.parameter] = f"{entity.hmtype}"
        pub_value_props = get_public_attributes_for_value_property(data_object=device)
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(data_object=device)
        assert pub_config_props

    custom_entities = []
    for device in central_pydevccu.devices:
        custom_entities.extend(device.custom_entities.values())

    ce_channels = {}
    for custom_entity in custom_entities:
        if custom_entity.device.device_type not in ce_channels:
            ce_channels[custom_entity.device.device_type] = []
        ce_channels[custom_entity.device.device_type].append(custom_entity.channel_no)
        pub_value_props = get_public_attributes_for_value_property(data_object=custom_entity)
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(data_object=custom_entity)
        assert pub_config_props

    entity_types = {}
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "hmtype"):
            if entity.hmtype not in entity_types:
                entity_types[entity.hmtype] = {}
            if type(entity).__name__ not in entity_types[entity.hmtype]:
                entity_types[entity.hmtype][type(entity).__name__] = []

            entity_types[entity.hmtype][type(entity).__name__].append(entity)
        pub_value_props = get_public_attributes_for_value_property(data_object=entity)
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(data_object=entity)
        assert pub_config_props

    parameters: list[tuple[str, int]] = []
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "parameter"):
            # if entity.device.device_type.startswith("HM-") and
            # if entity._attr_operations == 2:
            if (entity.parameter, entity._attr_operations) not in parameters:
                parameters.append((entity.parameter, entity._attr_operations))
    parameters = sorted(parameters)

    units = set()
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "unit"):
            units.add(entity.unit)

    usage_types: dict[HmEntityUsage, int] = {}
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "usage"):
            if entity.usage not in usage_types:
                usage_types[entity.usage] = 0
            counter = usage_types[entity.usage]
            usage_types[entity.usage] = counter + 1

    addresses: dict[str, str] = {}
    for address, device in central_pydevccu._devices.items():
        addresses[address] = f"{device.device_type}.json"

    with open(
        file=os.path.join(central_pydevccu.config.storage_folder, "all_devices.json"),
        mode="w",
        encoding=DEFAULT_ENCODING,
    ) as fptr:
        json.dump(addresses, fptr, indent=2)

    assert usage_types[HmEntityUsage.ENTITY_NO_CREATE] == 2713
    assert usage_types[HmEntityUsage.CE_PRIMARY] == 175
    assert usage_types[HmEntityUsage.ENTITY] == 3253
    assert usage_types[HmEntityUsage.CE_VISIBLE] == 96
    assert usage_types[HmEntityUsage.CE_SECONDARY] == 132

    assert len(ce_channels) == 110
    assert len(entity_types) == 6
    assert len(parameters) == 167

    assert len(central_pydevccu._devices) == 372
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central_pydevccu.delete_devices(const.PYDEVCCU_INTERFACE_ID, virtual_remotes)
    assert len(central_pydevccu._devices) == 369
    del_addresses = list(
        central_pydevccu.device_descriptions.get_device_descriptions(const.PYDEVCCU_INTERFACE_ID)
    )
    del_addresses = [adr for adr in del_addresses if ":" not in adr]
    await central_pydevccu.delete_devices(const.PYDEVCCU_INTERFACE_ID, del_addresses)
    assert len(central_pydevccu._devices) == 0
    assert len(central_pydevccu._entities) == 0
