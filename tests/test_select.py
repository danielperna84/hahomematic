"""Tests for select entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import EntityUsage
from hahomematic.platforms.generic import HmSelect
from hahomematic.platforms.hub import HmSysvarSelect

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU6354483": "HmIP-STHD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, False, False, None, None),
    ],
)
async def test_hmselect(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSelect."""
    central, mock_client, _ = central_client_factory
    select: HmSelect = cast(
        HmSelect,
        central.get_generic_entity("VCU6354483:1", "WINDOW_STATE"),
    )
    assert select.usage == EntityUsage.NO_CREATE
    assert select.unit is None
    assert select.min == "CLOSED"
    assert select.max == "OPEN"
    assert select.values == ("CLOSED", "OPEN")
    assert select.value == "CLOSED"
    await select.send_value("OPEN")
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6354483:1",
        paramset_key="VALUES",
        parameter="WINDOW_STATE",
        value=1,
    )
    assert select.value == "OPEN"
    await central.event(const.INTERFACE_ID, "VCU6354483:1", "WINDOW_STATE", 0)
    assert select.value == "CLOSED"

    await select.send_value(3)
    # do not write. value above max
    assert select.value == "CLOSED"

    await select.send_value(1)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6354483:1",
        paramset_key="VALUES",
        parameter="WINDOW_STATE",
        value=1,
    )
    # do not write. value above max
    assert select.value == "OPEN"

    call_count = len(mock_client.method_calls)
    await select.send_value(1)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio()
@pytest.mark.parametrize(
    (
        "address_device_translation",
        "do_mock_client",
        "add_sysvars",
        "add_programs",
        "ignore_devices_on_create",
        "un_ignore_list",
    ),
    [
        (TEST_DEVICES, True, True, False, None, None),
    ],
)
async def test_hmsysvarselect(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSysvarSelect."""
    central, mock_client, _ = central_client_factory
    select: HmSysvarSelect = cast(HmSysvarSelect, central.get_sysvar_entity("sv_list_ext"))
    assert select.usage == EntityUsage.ENTITY
    assert select.unit is None
    assert select.min is None
    assert select.max is None
    assert select.values == ("v1", "v2", "v3")
    assert select.value == "v1"
    await select.send_variable("v2")
    assert mock_client.method_calls[-1] == call.set_system_variable(name="sv_list_ext", value=1)
    assert select.value == "v2"
    await select.send_variable(3)
    # do not write. value above max
    assert select.value == "v2"
