"""Test the HaHomematic central."""
from __future__ import annotations

import json
import os

from const import CENTRAL_NAME
import pytest

from hahomematic.const import DEFAULT_ENCODING, HmEntityUsage
from hahomematic.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_value_property,
)
from hahomematic.entity import GenericEntity


@pytest.mark.asyncio
async def test_central(central_pydevccu, loop) -> None:
    """Test the central."""
    assert central_pydevccu
    assert central_pydevccu.name == CENTRAL_NAME
    assert central_pydevccu.model == "PyDevCCU"
    assert central_pydevccu.get_client(f"{CENTRAL_NAME}-BidCos-RF").model == "PyDevCCU"
    assert central_pydevccu.get_primary_client().model == "PyDevCCU"

    data = {}
    for device in central_pydevccu.devices.values():
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
    for device in central_pydevccu.devices.values():
        custom_entities.extend(device.custom_entities.values())

    ce_channels = {}
    for custom_entity in custom_entities:
        if custom_entity.device.device_type not in ce_channels:
            ce_channels[custom_entity.device.device_type] = []
        ce_channels[custom_entity.device.device_type].append(custom_entity.channel_no)
        pub_value_props = get_public_attributes_for_value_property(
            data_object=custom_entity
        )
        assert pub_value_props
        pub_config_props = get_public_attributes_for_config_property(
            data_object=custom_entity
        )
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

    parameters = []
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "parameter"):
            if entity.parameter not in parameters:
                parameters.append(entity.parameter)

    units = set()
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "_unit"):
            units.add(entity._unit)

    usage_types: dict[HmEntityUsage, int] = {}
    for entity in central_pydevccu._entities.values():
        if hasattr(entity, "usage"):
            if entity.usage not in usage_types:
                usage_types[entity.usage] = 0
            counter = usage_types[entity.usage]
            usage_types[entity.usage] = counter + 1

    switches: dict[str, set[int]] = {}

    for entity in central_pydevccu._entities.values():
        # if isinstance(entity, HmSwitchPlatform):
        if hasattr(entity, "parameter") and entity.parameter == "ON_TIME":
            device_type = entity.device.device_type[:8]
            if device_type.lower().startswith("hmip"):
                continue

            channel_no = entity.channel_no
            if device_type not in switches:
                switches[device_type] = set()
            switches[device_type].add(channel_no)

    entity_type_operations: dict[str, dict[str, set[int]]] = {}
    for entity in central_pydevccu._entities.values():
        if isinstance(entity, GenericEntity):
            if entity.platform not in entity_type_operations:
                entity_type_operations[entity.platform] = {}

            if entity.hmtype not in entity_type_operations[entity.platform]:
                entity_type_operations[entity.platform][entity.hmtype] = set()
            entity_type_operations[entity.platform][entity.hmtype].add(
                entity._attr_operations
            )
    addresses: dict[str, str] = {}
    for address, device in central_pydevccu.devices.items():
        addresses[address] = f"{device.device_type}.json"

    with open(
        file=os.path.join(central_pydevccu.config.storage_folder, "all_devices.json"),
        mode="w",
        encoding=DEFAULT_ENCODING,
    ) as fptr:
        json.dump(addresses, fptr, indent=2)

    assert usage_types[HmEntityUsage.ENTITY_NO_CREATE] == 2800
    assert usage_types[HmEntityUsage.CE_PRIMARY] == 175
    assert usage_types[HmEntityUsage.ENTITY] == 3618
    assert usage_types[HmEntityUsage.CE_VISIBLE] == 96
    assert usage_types[HmEntityUsage.CE_SECONDARY] == 132

    assert len(ce_channels) == 110
    assert len(entity_types) == 6
    assert len(parameters) == 189
