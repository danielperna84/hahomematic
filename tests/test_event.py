"""Tests for switch entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.const import EntityUsage, HomematicEventType
from hahomematic.platforms.event import ClickEvent, DeviceErrorEvent, ImpulseEvent

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU0000263": "HM-Sen-EP.json",
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
async def test_clickevent(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test ClickEvent."""
    central, _, factory = central_client_factory
    event: ClickEvent = cast(ClickEvent, central.get_event("VCU2128127:1", "PRESS_SHORT"))
    assert event.usage == EntityUsage.EVENT
    assert event.event_type == HomematicEventType.KEYPRESS
    await central.event(const.INTERFACE_ID, "VCU2128127:1", "PRESS_SHORT", True)
    assert factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.keypress",
        {
            "interface_id": const.INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 1,
            "model": "HmIP-BSM",
            "parameter": "PRESS_SHORT",
            "value": True,
        },
    )


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
async def test_impulseevent(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test ImpulseEvent."""
    central, _, factory = central_client_factory
    event: ImpulseEvent = cast(ImpulseEvent, central.get_event("VCU0000263:1", "SEQUENCE_OK"))
    assert event.usage == EntityUsage.EVENT
    assert event.event_type == HomematicEventType.IMPULSE
    await central.event(const.INTERFACE_ID, "VCU0000263:1", "SEQUENCE_OK", True)
    assert factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.impulse",
        {
            "interface_id": const.INTERFACE_ID,
            "address": "VCU0000263",
            "channel_no": 1,
            "model": "HM-Sen-EP",
            "parameter": "SEQUENCE_OK",
            "value": True,
        },
    )


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
async def test_deviceerrorevent(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test DeviceErrorEvent."""
    central, _, factory = central_client_factory
    event: DeviceErrorEvent = cast(
        DeviceErrorEvent,
        central.get_event("VCU2128127:0", "ERROR_OVERHEAT"),
    )
    assert event.usage == EntityUsage.EVENT
    assert event.event_type == HomematicEventType.DEVICE_ERROR
    await central.event(const.INTERFACE_ID, "VCU2128127:0", "ERROR_OVERHEAT", True)
    assert factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.device_error",
        {
            "interface_id": const.INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 0,
            "model": "HmIP-BSM",
            "parameter": "ERROR_OVERHEAT",
            "value": True,
        },
    )
