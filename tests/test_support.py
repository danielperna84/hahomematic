"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from hahomematic.caches.visibility import _get_value_from_dict_by_wildcard_key
from hahomematic.const import INIT_DATETIME, EntityUsage, ParameterType, SysvarType
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms.support import (
    _check_channel_name_with_channel_no,
    convert_value,
    generate_unique_id,
    get_custom_entity_name,
    get_device_name,
    get_entity_name,
    get_event_name,
)
from hahomematic.support import (
    build_headers,
    build_xml_rpc_uri,
    changed_within_seconds,
    check_or_create_directory,
    check_password,
    element_matches_key,
    find_free_port,
    get_channel_no,
    get_tls_context,
    parse_sys_var,
    to_bool,
)

from tests import helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU3609622": "HmIP-eTRV-2.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_generate_unique_id(factory: helper.Factory) -> None:
    """Test generate_unique_id."""
    central, _ = await factory.get_default_central({})
    assert (
        generate_unique_id(central=central, address="VCU2128127", parameter="LEVEL")
        == "vcu2128127_level"
    )
    assert (
        generate_unique_id(
            central=central, address="VCU2128127", parameter="LEVEL", prefix="PREFIX"
        )
        == "prefix_vcu2128127_level"
    )
    assert (
        generate_unique_id(central=central, address="INT0001", parameter="LEVEL")
        == "test1234_int0001_level"
    )


def test_build_xml_rpc_uri() -> None:
    """Test build_xml_rpc_uri."""
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path=None) == "http://1.2.3.4:80"
    assert build_xml_rpc_uri(host="1.2.3.4", port=80, path="group") == "http://1.2.3.4:80/group"
    assert (
        build_xml_rpc_uri(host="1.2.3.4", port=80, path="group", tls=True)
        == "https://1.2.3.4:80/group"
    )


def test_build_headers() -> None:
    """Test build_xml_rpc_uri."""
    assert build_headers(username="Martin", password="") == [
        ("Authorization", "Basic TWFydGluOg==")
    ]
    assert build_headers(username="", password="asdf") == [("Authorization", "Basic OmFzZGY=")]
    assert build_headers(username="Martin", password="asdf") == [
        ("Authorization", "Basic TWFydGluOmFzZGY=")
    ]


def test_check_or_create_directory() -> None:
    """Test check_or_create_directory."""
    assert check_or_create_directory(directory="") is False
    with patch(
        "os.path.exists",
        return_value=True,
    ):
        assert check_or_create_directory(directory="tmpdir_1") is True

    with (
        patch(
            "os.path.exists",
            return_value=False,
        ),
        patch(
            "os.makedirs",
            return_value=None,
        ),
    ):
        assert check_or_create_directory(directory="tmpdir_1") is True

    with (
        patch(
            "os.path.exists",
            return_value=False,
        ),
        patch("os.makedirs", side_effect=OSError("bla bla")),
    ):
        with pytest.raises(HaHomematicException) as exc:
            check_or_create_directory(directory="tmpdir_ex")
        assert exc


def test_parse_sys_var() -> None:
    """Test parse_sys_var."""
    assert parse_sys_var(data_type=None, raw_value="1.4") == "1.4"
    assert parse_sys_var(data_type=SysvarType.STRING, raw_value="1.4") == "1.4"
    assert parse_sys_var(data_type=SysvarType.FLOAT, raw_value="1.4") == 1.4
    assert parse_sys_var(data_type=SysvarType.INTEGER, raw_value="1") == 1
    assert parse_sys_var(data_type=SysvarType.ALARM, raw_value="true") is True
    assert parse_sys_var(data_type=SysvarType.LIST, raw_value="1") == 1
    assert parse_sys_var(data_type=SysvarType.LOGIC, raw_value="true") is True


@pytest.mark.asyncio
async def test_to_bool() -> None:
    """Test to_bool."""
    assert to_bool(value=True) is True
    assert to_bool(value="y") is True
    assert to_bool(value="yes") is True
    assert to_bool(value="t") is True
    assert to_bool(value="true") is True
    assert to_bool(value="on") is True
    assert to_bool(value="1") is True
    assert to_bool(value="") is False
    assert to_bool(value="n") is False
    assert to_bool(value="no") is False
    assert to_bool(value="f") is False
    assert to_bool(value="false") is False
    assert to_bool(value="off") is False
    assert to_bool(value="0") is False
    assert to_bool(value="blabla") is False
    assert to_bool(value="2") is False
    with pytest.raises(TypeError):
        to_bool(value=2)


@pytest.mark.asyncio
async def test_get_entity_name(factory: helper.Factory) -> None:
    """Test get_entity_name."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU2128127")
    name_data = get_entity_name(central=central, device=device, channel_no=4, parameter="LEVEL")
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Level"
    assert name_data.entity_name == "Level"

    central.device_details.add_name(address=f"{device.device_address}:5", name="Roof")
    name_data = get_entity_name(central=central, device=device, channel_no=5, parameter="LEVEL")
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"
    assert name_data.entity_name == "Roof Level"

    with patch(
        "hahomematic.platforms.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_entity_name(
            central=central, device=device, channel_no=5, parameter="LEVEL"
        )
        assert name_data.full_name == ""
        assert name_data.entity_name is None


@pytest.mark.asyncio
async def test_get_event_name(factory: helper.Factory) -> None:
    """Test get_event_name."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU2128127")
    name_data = get_event_name(central=central, device=device, channel_no=4, parameter="LEVEL")
    assert name_data.channel_name == "ch4"
    assert name_data.entity_name == "ch4 Level"
    assert name_data.full_name == "HmIP-BSM_VCU2128127 ch4 Level"

    central.device_details.add_name(address=f"{device.device_address}:5", name="Roof")
    name_data = get_event_name(central=central, device=device, channel_no=5, parameter="LEVEL")
    assert name_data.channel_name == "Roof"
    assert name_data.entity_name == "Roof Level"
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof Level"

    with patch(
        "hahomematic.platforms.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_event_name(central=central, device=device, channel_no=5, parameter="LEVEL")
        assert name_data.full_name == ""
        assert name_data.entity_name is None


@pytest.mark.asyncio
async def test_custom_entity_name(factory: helper.Factory) -> None:
    """Test get_custom_entity_name."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    device = central.get_device(address="VCU2128127")
    name_data = get_custom_entity_name(
        central=central,
        device=device,
        channel_no=4,
        is_only_primary_channel=True,
        usage=EntityUsage.CE_PRIMARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127"
    assert name_data.entity_name == ""

    name_data = get_custom_entity_name(
        central=central,
        device=device,
        channel_no=4,
        is_only_primary_channel=False,
        usage=EntityUsage.CE_SECONDARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 vch4"
    assert name_data.entity_name == "vch4"

    central.device_details.add_name(address=f"{device.device_address}:5", name="Roof")
    name_data = get_custom_entity_name(
        central=central,
        device=device,
        channel_no=5,
        is_only_primary_channel=True,
        usage=EntityUsage.CE_PRIMARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof"
    assert name_data.entity_name == "Roof"

    name_data = get_custom_entity_name(
        central=central,
        device=device,
        channel_no=5,
        is_only_primary_channel=False,
        usage=EntityUsage.CE_SECONDARY,
    )
    assert name_data.full_name == "HmIP-BSM_VCU2128127 Roof"
    assert name_data.entity_name == "Roof"

    with patch(
        "hahomematic.platforms.support._get_base_name_from_channel_or_device",
        return_value=None,
    ):
        name_data = get_custom_entity_name(
            central=central,
            device=device,
            channel_no=5,
            is_only_primary_channel=False,
            usage=EntityUsage.CE_SECONDARY,
        )
        assert name_data.full_name == ""
        assert name_data.entity_name is None


@pytest.mark.asyncio
async def test_get_device_name(factory: helper.Factory) -> None:
    """Test get_device_name."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    assert (
        get_device_name(central=central, device_address="VCU2128127", device_type="HmIP-BSM")
        == "HmIP-BSM_VCU2128127"
    )
    central.device_details.add_name(address="VCU2128127", name="Roof")
    assert (
        get_device_name(central=central, device_address="VCU2128127", device_type="HmIP-BSM")
        == "Roof"
    )


@pytest.mark.asyncio
async def test_tls_context() -> None:
    """Test tls_context."""
    assert get_tls_context(verify_tls=False).check_hostname is False
    assert get_tls_context(verify_tls=True).check_hostname is True


@pytest.mark.asyncio
async def test_changed_within_seconds() -> None:
    """Test updated_within_seconds."""
    assert (
        changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=10)), max_age=60)
        is True
    )
    assert (
        changed_within_seconds(last_change=(datetime.now() - timedelta(seconds=70)), max_age=60)
        is False
    )
    assert changed_within_seconds(last_change=INIT_DATETIME, max_age=60) is False


@pytest.mark.asyncio
async def test_convert_value() -> None:
    """Test convert_value."""
    assert convert_value(value=None, target_type=ParameterType.BOOL, value_list=None) is None
    assert convert_value(value=True, target_type=ParameterType.BOOL, value_list=None) is True
    assert convert_value(value="true", target_type=ParameterType.BOOL, value_list=None) is True
    assert (
        convert_value(value=1, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN"))
        is True
    )
    assert (
        convert_value(value=0, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN"))
        is False
    )
    assert (
        convert_value(value=2, target_type=ParameterType.BOOL, value_list=("CLOSED", "OPEN"))
        is False
    )
    assert convert_value(value="0.1", target_type=ParameterType.FLOAT, value_list=None) == 0.1
    assert convert_value(value="1", target_type=ParameterType.INTEGER, value_list=None) == 1
    assert convert_value(value="test", target_type=ParameterType.STRING, value_list=None) == "test"
    assert convert_value(value="1", target_type=ParameterType.STRING, value_list=None) == "1"
    assert convert_value(value=True, target_type=ParameterType.ACTION, value_list=None) is True


@pytest.mark.asyncio
async def test_element_matches_key() -> None:
    """Test element_matches_key."""
    assert element_matches_key(search_elements="HmIP-eTRV", compare_with=None) is False
    assert element_matches_key(search_elements="HmIP-eTRV", compare_with="HmIP-eTRV-2") is True
    assert (
        element_matches_key(
            search_elements="HmIP-eTRV",
            compare_with="HmIP-eTRV-2",
            do_wildcard_search=False,
        )
        is False
    )
    assert (
        element_matches_key(search_elements=["HmIP-eTRV", "HmIP-BWTH"], compare_with="HmIP-eTRV-2")
        is True
    )
    assert (
        element_matches_key(
            search_elements=["HmIP-eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV-2",
            do_wildcard_search=False,
        )
        is False
    )
    assert (
        element_matches_key(
            search_elements=["HmIP-eTRV", "HmIP-BWTH"],
            compare_with="HmIP-eTRV",
            do_wildcard_search=False,
        )
        is True
    )


@pytest.mark.asyncio
async def test_value_from_dict_by_wildcard_key() -> None:
    """Test value_from_dict_by_wildcard_key."""
    assert (
        _get_value_from_dict_by_wildcard_key(
            search_elements={"HmIP-eTRV": True}, compare_with=None
        )
        is None
    )
    assert (
        _get_value_from_dict_by_wildcard_key(
            search_elements={"HmIP-eTRV-2": True}, compare_with="HmIP-eTRV"
        )
        is True
    )
    assert (
        _get_value_from_dict_by_wildcard_key(
            search_elements={"HmIP-eTRV-2": False},
            compare_with="HmIP-eTRV",
            do_wildcard_search=False,
        )
        is None
    )
    assert (
        _get_value_from_dict_by_wildcard_key(
            search_elements={"HmIP-eTRV-2": False},
            compare_with="HmIP-eTRV-2",
            do_wildcard_search=False,
        )
        is False
    )


@pytest.mark.asyncio
async def test_others() -> None:
    """Test find_free_port."""
    assert find_free_port()
    assert get_channel_no(address="12312:1") == 1
    assert get_channel_no(address="12312") is None
    assert _check_channel_name_with_channel_no(name="light:1") is True
    assert _check_channel_name_with_channel_no(name="light:Test") is False
    assert _check_channel_name_with_channel_no(name="light:Test:123") is False


def test_password() -> None:
    """
    Test the password.

    Password can be empty.
    Allowed characters:
        - A-Z, a-z
        - 0-9
        - ., !, $, (, ), :, ;, #, -
    """
    assert check_password(None) is False
    assert check_password("") is True
    assert check_password("t") is True
    assert check_password("test") is True
    assert check_password("TEST") is True
    assert check_password("1234") is True
    assert check_password("test123TEST") is True
    assert check_password("test.!$():;#-") is True
    assert check_password("test%") is False
