"""Tests for devices of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_generic_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.text import HmText

TEST_DEVICES = {}


@pytest.mark.asyncio
async def test_empty(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmText. There are currently no text entities"""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central


# TODO: Add device related tests, available, unreach
