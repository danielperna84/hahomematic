"""Tests for text entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_hm_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.text import HmText

TEST_DEVICES: dict[str, str] = {}


@pytest.mark.asyncio
async def no_test_hmtext(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmText. There are currently no text entities"""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    text: HmText = cast(
        HmText, await get_hm_generic_entity(central, "VCU7981740:1", "STATE")
    )
    assert text.usage == HmEntityUsage.ENTITY


# TODO: Add test for sysvar
