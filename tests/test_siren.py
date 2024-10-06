"""Tests for siren entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.config import WAIT_FOR_CALLBACK
from hahomematic.const import EntityUsage
from hahomematic.platforms.custom import CeIpSiren, CeIpSirenSmoke

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU8249617": "HmIP-ASIR-2.json",
    "VCU2822385": "HmIP-SWSD.json",
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
async def test_ceipsiren(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeIpSiren."""
    central, mock_client, _ = central_client_factory
    siren: CeIpSiren = cast(CeIpSiren, helper.get_prepared_custom_entity(central, "VCU8249617", 3))
    assert siren.usage == EntityUsage.CE_PRIMARY
    assert siren.service_method_names == ("turn_off", "turn_on")

    assert siren.is_on is False
    await central.event(const.INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    await central.event(const.INTERFACE_ID, "VCU8249617:3", "ACOUSTIC_ALARM_ACTIVE", 0)
    assert siren.is_on is False
    await central.event(const.INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 1)
    assert siren.is_on is True
    await central.event(const.INTERFACE_ID, "VCU8249617:3", "OPTICAL_ALARM_ACTIVE", 0)
    assert siren.is_on is False

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU8249617:3",
        paramset_key="VALUES",
        values={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_on(
        acoustic_alarm="FREQUENCY_RISING_AND_FALLING",
        optical_alarm="BLINKING_ALTERNATELY_REPEATING",
        duration=30,
    )
    assert mock_client.method_calls[-2] == call.put_paramset(
        channel_address="VCU8249617:3",
        paramset_key="VALUES",
        values={
            "ACOUSTIC_ALARM_SELECTION": 3,
            "OPTICAL_ALARM_SELECTION": 1,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 30,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
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
        channel_address="VCU8249617:3",
        paramset_key="VALUES",
        values={
            "ACOUSTIC_ALARM_SELECTION": 0,
            "OPTICAL_ALARM_SELECTION": 0,
            "DURATION_UNIT": 0,
            "DURATION_VALUE": 0,
        },
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_off()
    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)


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
async def test_ceipsirensmoke(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeIpSirenSmoke."""
    central, mock_client, _ = central_client_factory
    siren: CeIpSirenSmoke = cast(
        CeIpSirenSmoke, helper.get_prepared_custom_entity(central, "VCU2822385", 1)
    )
    assert siren.usage == EntityUsage.CE_PRIMARY

    assert siren.is_on is False
    await central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 1)
    assert siren.is_on is True
    await central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 2)
    assert siren.is_on is True
    await central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 3)
    assert siren.is_on is True
    await central.event(const.INTERFACE_ID, "VCU2822385:1", "SMOKE_DETECTOR_ALARM_STATUS", 0)
    assert siren.is_on is False

    await siren.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key="VALUES",
        parameter="SMOKE_DETECTOR_COMMAND",
        value=2,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await siren.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2822385:1",
        paramset_key="VALUES",
        parameter="SMOKE_DETECTOR_COMMAND",
        value=1,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    call_count = len(mock_client.method_calls)
    await siren.turn_off()
    assert (call_count + 1) == len(mock_client.method_calls)
