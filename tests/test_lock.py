"""Tests for button entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.custom.lock import CeIpLock, CeRfLock

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU9724704": "HmIP-DLD.json",
    "VCU0000146": "HM-Sec-Key.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_cerflock(factory: helper.Factory) -> None:
    """Test CeRfLock."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    lock: CeRfLock = cast(CeRfLock, helper.get_prepared_custom_entity(central, "VCU0000146", 1))
    assert lock.usage == EntityUsage.CE_PRIMARY

    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="STATE",
        value=True,
    )
    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="STATE",
        value=False,
    )
    assert lock.is_locked is True
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000146:1",
        paramset_key="VALUES",
        parameter="OPEN",
        value=True,
    )

    assert lock.is_locking is None
    central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 2)
    assert lock.is_locking is True
    central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 1)
    assert lock.is_unlocking is True
    central.event(const.INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False
    central.event(const.INTERFACE_ID, "VCU0000146:1", "ERROR", 2)
    assert lock.is_jammed is True

    central.event(const.INTERFACE_ID, "VCU0000146:1", "ERROR", 0)

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
    assert (call_count + 1) == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceiplock(factory: helper.Factory) -> None:
    """Test CeIpLock."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    lock: CeIpLock = cast(CeIpLock, helper.get_prepared_custom_entity(central, "VCU9724704", 1))
    assert lock.usage == EntityUsage.CE_PRIMARY

    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=0,
    )
    central.event(const.INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 1)
    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=1,
    )
    central.event(const.INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 2)
    assert lock.is_locked is False
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=2,
    )

    assert lock.is_locking is None
    central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 2)
    assert lock.is_locking is True
    central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 1)
    assert lock.is_unlocking is True
    central.event(const.INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False

    await lock.open()
    call_count = len(mock_client.method_calls)
    await lock.open()
    assert (call_count + 1) == len(mock_client.method_calls)
