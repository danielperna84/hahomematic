"""Tests for siren entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.custom.siren import CeIpSiren, CeIpSirenSmoke

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU8249617": "HmIP-ASIR-2.json",
    "VCU2822385": "HmIP-SWSD.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_ceipsiren(factory: helper.Factory) -> None:
    """Test CeIpSiren."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    siren: CeIpSiren = cast(CeIpSiren, helper.get_prepared_custom_entity(central, "VCU8249617", 3))
    assert siren.usage == EntityUsage.CE_PRIMARY

    assert siren.is_on is False
    central.event(const.INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    central.event(const.INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 0)
    assert siren.is_on is False
    central.event(const.INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    central.event(const.INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 0)
    assert siren.is_on is False

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU8249617:3",
        paramset_key="VALUES",
        value={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
    )

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU8249617:3",
        paramset_key="VALUES",
        value={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
    )

    with pytest.raises(ValueError):
        await siren.turn_on(
            acoustic_alarm="not_in_list",
            optical_alarm="BLINKING_ALTERNATELY_REPEATING",
            duration=30,
        )

    with pytest.raises(ValueError):
        await siren.turn_on(
            acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
            optical_alarm="not_in_list",
            duration=30,
        )

    await siren.turn_off()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU8249617:3",
        paramset_key="VALUES",
        value={
            "ACOUSTIC_ALARM_SELECTION": 0,
            "OPTICAL_ALARM_SELECTION": 0,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 0,
        },
    )

    await siren.turn_off()
    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipsirensmoke(factory: helper.Factory) -> None:
    """Test CeIpSirenSmoke."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    siren: CeIpSirenSmoke = cast(
        CeIpSirenSmoke, helper.get_prepared_custom_entity(central, "VCU2822385", 1)
    )
    assert siren.usage == EntityUsage.CE_PRIMARY

    assert siren.is_on is False
    central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 1)
    assert siren.is_on is True
    central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 2)
    assert siren.is_on is True
    central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 3)
    assert siren.is_on is True
    central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 0)
    assert siren.is_on is False

    await siren.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key="VALUES",
        parameter="SMOKE_DETECTOR_COMMAND",
        value=2,
    )

    await siren.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key="VALUES",
        parameter="SMOKE_DETECTOR_COMMAND",
        value=1,
    )

    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)
