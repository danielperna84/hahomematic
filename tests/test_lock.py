"""Tests for button entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import Mock, call

import pytest

from hahomematic.central import CentralUnit
from hahomematic.client import Client
from hahomematic.config import WAIT_FOR_CALLBACK
from hahomematic.const import EntityUsage
from hahomematic.platforms.custom import CeIpLock, CeRfLock

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU9724704": "HmIP-DLD.json",
    "VCU0000146": "HM-Sec-Key.json",
    "VCU3609622": "HmIP-eTRV-2.json",
    "VCU0000341": "HM-TC-IT-WM-W-EU.json",
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
async def test_cerflock(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeRfLock."""
    central, mock_client, _ = central_client_factory
    lock: CeRfLock = cast(CeRfLock, helper.get_prepared_custom_entity(central, "VCU0000146", 1))
    assert lock.usage == EntityUsage.CE_PRIMARY

    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    assert lock.is_locked is True
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="OPEN",
        value=True,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert lock.is_locking is None
    await central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 2)
    assert lock.is_locking is True
    await central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    await central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 1)
    assert lock.is_unlocking is True
    await central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False
    await central.event(const.INTERFACE_ID, "VCU0000146:1", "ERROR", 2)
    assert lock.is_jammed is True

    await central.event(const.INTERFACE_ID, "VCU0000146:1", "ERROR", 0)

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
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
async def test_ceiplock(
    central_client_factory: tuple[CentralUnit, Client | Mock, helper.Factory],
) -> None:
    """Test CeIpLock."""
    central, mock_client, _ = central_client_factory
    lock: CeIpLock = cast(CeIpLock, helper.get_prepared_custom_entity(central, "VCU9724704", 1))
    assert lock.usage == EntityUsage.CE_PRIMARY
    assert lock.service_method_names == ("lock", "open", "unlock")

    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=0,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 1)
    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=1,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 2)
    assert lock.is_locked is False
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=2,
        wait_for_callback=WAIT_FOR_CALLBACK,
    )

    assert lock.is_locking is None
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 2)
    assert lock.is_locking is True
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 1)
    assert lock.is_unlocking is True
    await central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
    assert (call_count + 1) == len(mock_client.method_calls)
