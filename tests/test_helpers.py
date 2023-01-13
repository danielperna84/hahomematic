"""Tests for switch entities of hahomematic."""
from __future__ import annotations

import asyncio
from typing import cast
from unittest.mock import MagicMock, call

import const
import helper
from helper import get_custom_entity, get_device, get_generic_entity, get_wrapper_entity
import pytest

from hahomematic.const import (
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
)
from hahomematic.helpers import (
    build_headers,
    build_xml_rpc_uri,
    generate_unique_identifier,
    get_custom_entity_name,
    get_device_name,
    get_entity_name,
    get_event_name,
    parse_sys_var,
    to_bool,
)

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}


@pytest.mark.asyncio
async def test_generate_unique_identifier(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test generate_unique_identifier."""
    central, mock_client = await central_local_factory.get_central({})
    assert (
        generate_unique_identifier(
            central=central, address="VCU2128127", parameter="LEVEL"
        )
        == "vcu2128127_level"
    )
    assert (
        generate_unique_identifier(
            central=central, address="VCU2128127", parameter="LEVEL", prefix="PREFIX"
        )
        == "prefix_vcu2128127_level"
    )
    assert (
        generate_unique_identifier(
            central=central, address="INT0001", parameter="LEVEL"
        )
        == "test1234_int0001_level"
    )


@pytest.mark.asyncio
async def test_build_xml_rpc_uri() -> None:
    """Test build_xml_rpc_uri."""
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path=None) == "http://1.2.3.4:80"
    assert (
        build_xml_rpc_uri(host="1.2.3.4", port=80, path="group")
        == "http://1.2.3.4:80/group"
    )
    assert (
        build_xml_rpc_uri(host="1.2.3.4", port=80, path="group", tls=True)
        == "https://1.2.3.4:80/group"
    )


@pytest.mark.asyncio
async def test_build_headers() -> None:
    """Test build_xml_rpc_uri."""
    assert build_headers() == [("Authorization", "Basic Tm9uZTpOb25l")]
    assert build_headers(username="Martin") == [
        ("Authorization", "Basic TWFydGluOk5vbmU=")
    ]
    assert build_headers(password="asdf") == [("Authorization", "Basic Tm9uZTphc2Rm")]
    assert build_headers(username="Martin", password="asdf") == [
        ("Authorization", "Basic TWFydGluOmFzZGY=")
    ]


@pytest.mark.asyncio
async def test_check_or_create_directory() -> None:
    """Test check_or_create_directory."""


@pytest.mark.asyncio
async def test_parse_sys_var() -> None:
    """Test parse_sys_var."""
    assert parse_sys_var(data_type=None, raw_value="1.4") == "1.4"
    assert parse_sys_var(data_type=SYSVAR_HM_TYPE_FLOAT, raw_value="1.4") == 1.4
    assert parse_sys_var(data_type=SYSVAR_HM_TYPE_INTEGER, raw_value="1") == 1
    assert parse_sys_var(data_type=SYSVAR_TYPE_ALARM, raw_value="true") == True
    assert parse_sys_var(data_type=SYSVAR_TYPE_LIST, raw_value="1") == 1
    assert parse_sys_var(data_type=SYSVAR_TYPE_LOGIC, raw_value="true") == True


@pytest.mark.asyncio
async def test_to_bool() -> None:
    """Test to_bool."""
    assert to_bool(value=True) == True
    assert to_bool(value="y") == True
    assert to_bool(value="yes") == True
    assert to_bool(value="t") == True
    assert to_bool(value="true") == True
    assert to_bool(value="on") == True
    assert to_bool(value="1") == True
    assert to_bool(value="n") == False
    assert to_bool(value="no") == False
    assert to_bool(value="f") == False
    assert to_bool(value="false") == False
    assert to_bool(value="off") == False
    assert to_bool(value="0") == False
    with pytest.raises(ValueError):
        to_bool(value=2)


@pytest.mark.asyncio
async def test_get_entity_name(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test get_entity_name."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    device = get_device(central_unit=central, address="VCU2128127")
    assert (
        get_entity_name(
            central=central, device=device, channel_no=4, parameter="LEVEL"
        ).full_name
        == "HmIP-BSM_VCU2128127 Level"
    )
    assert (
        get_entity_name(
            central=central, device=device, channel_no=4, parameter="LEVEL"
        ).entity_name
        == "Level"
    )
    central.device_details.add_name(address=f"{device.device_address}:5", name="Roof")
    assert (
        get_entity_name(
            central=central, device=device, channel_no=5, parameter="LEVEL"
        ).full_name
        == "HmIP-BSM_VCU2128127 Roof Level"
    )
    assert (
        get_entity_name(
            central=central, device=device, channel_no=5, parameter="LEVEL"
        ).entity_name
        == "Roof Level"
    )


@pytest.mark.asyncio
async def test_get_event_name() -> None:
    """Test get_event_name."""


@pytest.mark.asyncio
async def test_custom_entity_name() -> None:
    """Test custom_entity_name."""


@pytest.mark.asyncio
async def test_check_channel_name_with_channel_no() -> None:
    """Test check_channel_name_with_channel_no."""


@pytest.mark.asyncio
async def test_check_channel_is_the_only_primary_channel() -> None:
    """Test check_channel_is_the_only_primary_channel."""


@pytest.mark.asyncio
async def test_tls_context() -> None:
    """Test tls_context."""


@pytest.mark.asyncio
async def test_updated_within_seconds() -> None:
    """Test updated_within_seconds."""


@pytest.mark.asyncio
async def test_convert_value() -> None:
    """Test convert_value."""


@pytest.mark.asyncio
async def test_find_free_port() -> None:
    """Test find_free_port."""


@pytest.mark.asyncio
async def test_element_matches_key() -> None:
    """Test element_matches_key."""


@pytest.mark.asyncio
async def test_value_from_dict_by_wildcard_key() -> None:
    """Test value_from_dict_by_wildcard_key."""
