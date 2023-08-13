"""Tests for switch entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import HmEntityUsage, HmEventType
from hahomematic.platforms.event import ClickEvent, DeviceErrorEvent, ImpulseEvent

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU2128127": "HmIP-BSM.json",
    "VCU0000263": "HM-Sen-EP.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_clickevent(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test ClickEvent."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    event: ClickEvent = cast(ClickEvent, central.get_event("VCU2128127:1", "PRESS_SHORT"))
    assert event.usage == HmEntityUsage.EVENT
    assert event.event_type == HmEventType.KEYPRESS
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:1", "PRESS_SHORT", True)
    assert central_local_factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.keypress",
        {
            "interface_id": const.LOCAL_INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 1,
            "device_type": "HmIP-BSM",
            "parameter": "PRESS_SHORT",
            "value": True,
        },
    )


@pytest.mark.asyncio
async def test_impulseevent(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test ImpulseEvent."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    event: ImpulseEvent = cast(ImpulseEvent, central.get_event("VCU0000263:1", "SEQUENCE_OK"))
    assert event.usage == HmEntityUsage.EVENT
    assert event.event_type == HmEventType.IMPULSE
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000263:1", "SEQUENCE_OK", True)
    assert central_local_factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.impulse",
        {
            "interface_id": const.LOCAL_INTERFACE_ID,
            "address": "VCU0000263",
            "channel_no": 1,
            "device_type": "HM-Sen-EP",
            "parameter": "SEQUENCE_OK",
            "value": True,
        },
    )


@pytest.mark.asyncio
async def test_deviceerrorevent(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test DeviceErrorEvent."""
    central, _ = await central_local_factory.get_default_central(TEST_DEVICES)
    event: DeviceErrorEvent = cast(
        DeviceErrorEvent,
        central.get_event("VCU2128127:0", "ERROR_OVERHEAT"),
    )
    assert event.usage == HmEntityUsage.EVENT
    assert event.event_type == HmEventType.DEVICE_ERROR
    central.event(const.LOCAL_INTERFACE_ID, "VCU2128127:0", "ERROR_OVERHEAT", True)
    assert central_local_factory.ha_event_mock.call_args_list[-1] == call(
        "homematic.device_error",
        {
            "interface_id": const.LOCAL_INTERFACE_ID,
            "address": "VCU2128127",
            "channel_no": 0,
            "device_type": "HmIP-BSM",
            "parameter": "ERROR_OVERHEAT",
            "value": True,
        },
    )
