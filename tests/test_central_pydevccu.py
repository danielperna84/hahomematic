"""Test the HaHomematic central."""

from __future__ import annotations

import os

import orjson
import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_value_property,
)
from hahomematic.platforms.generic.entity import GenericEntity

from tests import const

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_central_mini(central_unit_mini) -> None:
    """Test the central."""
    assert central_unit_mini
    assert central_unit_mini.name == const.CENTRAL_NAME
    assert central_unit_mini.model == "PyDevCCU"
    assert central_unit_mini.get_client(const.INTERFACE_ID).model == "PyDevCCU"
    assert central_unit_mini.primary_client.model == "PyDevCCU"
    assert len(central_unit_mini._devices) == 1
    assert len(central_unit_mini.get_entities(exclude_no_create=False)) == 29


@pytest.mark.asyncio
async def test_central_full(central_unit_full) -> None:
    """Test the central."""
    assert central_unit_full
    assert central_unit_full.name == const.CENTRAL_NAME
    assert central_unit_full.model == "PyDevCCU"
    assert central_unit_full.get_client(const.INTERFACE_ID).model == "PyDevCCU"
    assert central_unit_full.primary_client.model == "PyDevCCU"

    data = {}
    for device in central_unit_full.devices:
        if device.device_type not in data:
            data[device.device_type] = {}
        for entity in device.generic_entities:
            if entity.parameter not in data[device.device_type]:
                data[device.device_type][entity.parameter] = f"{entity.hmtype}"
        pub_value_props = get_public_attributes_for_value_property(data_object=device)
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(data_object=device)
        assert pub_config_props

    custom_entities = []
    for device in central_unit_full.devices:
        custom_entities.extend(device.custom_entities)

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
    for entity in central_unit_full.get_entities(exclude_no_create=False):
        if hasattr(entity, "hmtype"):
            if entity.hmtype not in entity_types:
                entity_types[entity.hmtype] = {}
            if type(entity).__name__ not in entity_types[entity.hmtype]:
                entity_types[entity.hmtype][type(entity).__name__] = []

            entity_types[entity.hmtype][type(entity).__name__].append(entity)

        if isinstance(entity, GenericEntity):
            pub_value_props = get_public_attributes_for_value_property(data_object=entity)
            assert pub_value_props
            pub_config_props = get_public_attributes_for_config_property(data_object=entity)
            assert pub_config_props

    parameters: list[tuple[str, int]] = []
    for entity in central_unit_full.get_entities(exclude_no_create=False):
        if (
            hasattr(entity, "parameter")
            and (entity.parameter, entity._operations) not in parameters
        ):
            parameters.append((entity.parameter, entity._operations))
    parameters = sorted(parameters)

    units = set()
    for entity in central_unit_full.get_entities(exclude_no_create=False):
        if hasattr(entity, "unit"):
            units.add(entity.unit)

    usage_types: dict[EntityUsage, int] = {}
    for entity in central_unit_full.get_entities(exclude_no_create=False):
        if hasattr(entity, "usage"):
            if entity.usage not in usage_types:
                usage_types[entity.usage] = 0
            counter = usage_types[entity.usage]
            usage_types[entity.usage] = counter + 1

    addresses: dict[str, str] = {}
    for address, device in central_unit_full._devices.items():
        addresses[address] = f"{device.device_type}.json"

    with open(
        file=os.path.join(central_unit_full.config.storage_folder, "all_devices.json"),
        mode="wb",
    ) as fptr:
        fptr.write(orjson.dumps(addresses, option=orjson.OPT_INDENT_2 | orjson.OPT_NON_STR_KEYS))

    assert usage_types[EntityUsage.NO_CREATE] == 3122
    assert usage_types[EntityUsage.CE_PRIMARY] == 194
    assert usage_types[EntityUsage.ENTITY] == 3799
    assert usage_types[EntityUsage.CE_VISIBLE] == 102
    assert usage_types[EntityUsage.CE_SECONDARY] == 146

    assert len(ce_channels) == 118
    assert len(entity_types) == 6
    assert len(parameters) == 215

    assert len(central_unit_full._devices) == 383
    virtual_remotes = ["VCU4264293", "VCU0000057", "VCU0000001"]
    await central_unit_full.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=virtual_remotes
    )
    assert len(central_unit_full._devices) == 380
    del_addresses = list(
        central_unit_full.device_descriptions.get_device_descriptions(const.INTERFACE_ID)
    )
    del_addresses = [adr for adr in del_addresses if ":" not in adr]
    await central_unit_full.delete_devices(
        interface_id=const.INTERFACE_ID, addresses=del_addresses
    )
    assert len(central_unit_full._devices) == 0
    assert len(central_unit_full.get_entities(exclude_no_create=False)) == 0
