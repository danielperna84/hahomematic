"""Tests for text entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import EntityUsage
from hahomematic.platforms.generic import HmText
from hahomematic.platforms.hub import HmSysvarText

from tests import helper

TEST_DEVICES: dict[str, str] = {}

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
async def no_test_hmtext(central_client: tuple[CentralUnit, Client | Mock]) -> None:
    """Test HmText. There are currently no text entities."""
    central, _ = central_client
    text: HmText = cast(HmText, central.get_generic_entity("VCU7981740:1", "STATE"))
    assert text.usage == EntityUsage.ENTITY


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
        ({}, True, True, False, None, None),
    ],
)
async def test_hmsysvartext(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSysvarText. There are currently no text entities."""
    central, mock_client, _ = central_client_factory
    text: HmSysvarText = cast(HmSysvarText, central.get_sysvar_entity("sv_string_ext"))
    assert text.usage == EntityUsage.ENTITY

    assert text.unit is None
    assert text.values is None
    assert text.value == "test1"
    await text.send_variable("test23")
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_string_ext", value="test23"
    )
    assert text.value == "test23"
