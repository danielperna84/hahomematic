"""Tests for siren entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.siren import CeIpSiren

TEST_DEVICES: dict[str, str] = {
    "VCU8249617": "HmIP-ASIR-2.json",
}


@pytest.mark.asyncio
async def test_ceipsiren(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpSiren."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    siren: CeIpSiren = cast(CeIpSiren, await helper.get_custom_entity(central, "VCU8249617", 3))
    assert siren.usage == HmEntityUsage.CE_PRIMARY

    assert siren.is_on is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 0)
    assert siren.is_on is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 0)
    assert siren.is_on is False

    await siren.turn_on("FREQUENCY_RISING_AND_FALLING", "BLINKING_ALTERNATELY_REPEATING", 30)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU8249617:3",
        paramset_key="VALUES",
        value={
            "ACOUSTIC_ALARM_SELECTION": "FREQUENCY_RISING_AND_FALLING",
            "OPTICAL_ALARM_SELECTION": "BLINKING_ALTERNATELY_REPEATING",
            "DURATION_UNIT": "S",
            "DURATION_VALUE": 30,
        },
    )
