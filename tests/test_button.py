"""Tests for button entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.generic_platforms.button import HmButton, HmProgramButton
from hahomematic.helpers import ProgramData

TEST_DEVICES: dict[str, str] = {
    "VCU1437294": "HmIP-SMI.json",
}


@pytest.mark.asyncio
async def test_hmbutton(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmButton."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    button: HmButton = cast(
        HmButton,
        await helper.get_generic_entity(central, "VCU1437294:1", "RESET_MOTION"),
    )
    assert button.usage == HmEntityUsage.ENTITY
    assert button.available is True
    assert button.is_readable is False
    assert button.value is None
    assert button.value_list is None
    assert button.hmtype == "ACTION"
    await button.press()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1437294:1",
        paramset_key="VALUES",
        parameter="RESET_MOTION",
        value=True,
    )

    call_count = len(mock_client.method_calls)
    await button.press()
    assert (call_count + 1) == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_hmprogrambutton(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test HmProgramButton."""
    central, mock_client = await central_local_factory.get_default_central({}, add_programs=True)
    button: HmProgramButton = cast(
        HmProgramButton, await helper.get_program_button(central, "pid1")
    )
    assert button.usage == HmEntityUsage.ENTITY
    assert button.available is True
    assert button.is_active is True
    assert button.is_internal is False
    assert button.ccu_program_name == "p1"
    assert button.name == "P_P1"
    await button.press()
    assert mock_client.method_calls[-1] == call.execute_program(pid="pid1")
    updated_program = ProgramData(
        name="p1",
        pid="pid1",
        is_active=False,
        is_internal=True,
        last_execute_time="1900-1-1",
    )
    button.update_data(updated_program)
    assert button.is_active is False
    assert button.is_internal is True

    button2: HmProgramButton = cast(
        HmProgramButton, await helper.get_program_button(central, "pid2")
    )
    assert button2.usage == HmEntityUsage.ENTITY
    assert button2.is_active is False
    assert button2.is_internal is False
    assert button2.ccu_program_name == "p_2"
    assert button2.name == "P_2"
