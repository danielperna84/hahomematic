"""Tests for text entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.text import HmSysvarText, HmText

TEST_DEVICES: dict[str, str] = {}


@pytest.mark.asyncio
async def no_test_hmtext(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmText. There are currently no text entities"""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    text: HmText = cast(HmText, await helper.get_generic_entity(central, "VCU7981740:1", "STATE"))
    assert text.usage == HmEntityUsage.ENTITY


@pytest.mark.asyncio
async def test_hmsysvartext(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmSysvarText. There are currently no text entities"""
    central, mock_client = await central_local_factory.get_default_central({}, add_sysvars=True)
    text: HmSysvarText = cast(
        HmSysvarText, await helper.get_sysvar_entity(central, "sv_string_ext")
    )
    assert text.usage == HmEntityUsage.ENTITY

    assert text.unit is None
    assert text.value_list is None
    assert text.value == "test1"
    await text.send_variable("test23")
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_string_ext", value="test23"
    )
    assert text.value == "test23"
