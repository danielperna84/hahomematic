"""Tests for text entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.generic.text import HmText
from hahomematic.platforms.hub.text import HmSysvarText

from tests import helper

TEST_DEVICES: dict[str, str] = {}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def no_test_hmtext(factory: helper.Factory) -> None:
    """Test HmText. There are currently no text entities."""
    central, _ = await factory.get_default_central(TEST_DEVICES)
    text: HmText = cast(HmText, central.get_generic_entity("VCU7981740:1", "STATE"))
    assert text.usage == EntityUsage.ENTITY


@pytest.mark.asyncio
async def test_hmsysvartext(factory: helper.Factory) -> None:
    """Test HmSysvarText. There are currently no text entities."""
    central, mock_client = await factory.get_default_central({}, add_sysvars=True)
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
