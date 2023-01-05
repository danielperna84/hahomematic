"""Tests for button entities of hahomematic."""
from __future__ import annotations

from typing import cast

import const
import helper
from helper import get_hm_generic_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.button import HmButton

TEST_DEVICES: dict[str, str] = {
    "VCU1437294": "HmIP-SMI.json",
}


@pytest.mark.asyncio
async def test_hmbutton(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmButton."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    button: HmButton = cast(
        HmButton, await get_hm_generic_entity(central, "VCU1437294:1", "RESET_MOTION")
    )
    assert button.usage == HmEntityUsage.ENTITY
    assert button.is_readable is False
    assert button.value is None
    assert button.value_list is None
    assert button.hmtype == "ACTION"
    assert button.press()
    assert button.value is None
