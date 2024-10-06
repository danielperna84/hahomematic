"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.config import WAIT_FOR_CALLBACK
from hahomematic.const import EntityUsage
from hahomematic.platforms.custom import CeSwitch
from hahomematic.platforms.generic import HmSwitch
from hahomematic.platforms.hub import HmSysvarSwitch

from tests import helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
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
async def test_ceswitch(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeSwitch."""
    central, mock_client, _ = central_client_factory
    switch: CeSwitch = cast(CeSwitch, helper.get_prepared_custom_entity(central, "VCU2128127", 4))
    assert switch.usage == EntityUsage.CE_PRIMARY
    assert switch.service_method_names == ("turn_off", "turn_on")

    await switch.turn_off()
    assert switch.value is False
    assert switch.channel_value is False
    await switch.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert switch.value is True
    await switch.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert switch.value is False
    await switch.turn_on(on_time=60)
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        values={"ON_TIME": 60.0, "STATE": True},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert switch.value is True

    await switch.turn_off()
    switch.set_on_time(35.4)
    await switch.turn_on()
    assert mock_client.method_calls[-1] == call.put_paramset(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        values={"ON_TIME": 35.4, "STATE": True},
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    await switch.turn_on()
    call_count = len(mock_client.method_calls)
    await switch.turn_on()
    assert call_count == len(mock_client.method_calls)

    await switch.turn_off()
    call_count = len(mock_client.method_calls)
    await switch.turn_off()
    assert call_count == len(mock_client.method_calls)


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
async def test_hmswitch(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSwitch."""
    central, mock_client, _ = central_client_factory
    switch: HmSwitch = cast(HmSwitch, central.get_generic_entity("VCU2128127:4", "STATE"))
    assert switch.usage == EntityUsage.NO_CREATE
    assert switch.service_method_names == (
        "send_value",
        "set_on_time",
        "turn_off",
        "turn_on",
    )

    assert switch.value is None
    await switch.turn_on()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.turn_off()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
    )
    assert switch.value is False
    await switch.turn_on(on_time=60)
    assert mock_client.method_calls[-2] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=60.0,
    )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert switch.value is True
    await switch.set_on_time(35.4)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU2128127:4",
        paramset_key="VALUES",
        parameter="ON_TIME",
        value=35.4,
    )

    await switch.turn_on()
    call_count = len(mock_client.method_calls)
    await switch.turn_on()
    assert call_count == len(mock_client.method_calls)

    await switch.turn_off()
    call_count = len(mock_client.method_calls)
    await switch.turn_off()
    assert call_count == len(mock_client.method_calls)


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
async def test_hmsysvarswitch(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test HmSysvarSwitch."""
    central, mock_client, _ = central_client_factory
    switch: HmSysvarSwitch = cast(HmSysvarSwitch, central.get_sysvar_entity("sv_alarm_ext"))
    assert switch.usage == EntityUsage.ENTITY

    assert switch.value is False
    await switch.send_variable(True)
    assert mock_client.method_calls[-1] == call.set_system_variable(
        name="sv_alarm_ext", value=True
    )
