"""Tests for button entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_hm_custom_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.lock import CeIpLock, CeRfLock

TEST_DEVICES: dict[str, str] = {
    "VCU9724704": "HmIP-DLD.json",
    "VCU0000146": "HM-Sec-Key.json",
}


@pytest.mark.asyncio
async def test_cerflock(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeRfLock."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    lock: CeRfLock = cast(
        CeRfLock, await get_hm_custom_entity(central, "VCU0000146", 1)
    )
    assert lock.usage == HmEntityUsage.CE_PRIMARY

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
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000146:1", "DIRECTION", 2)
    assert lock.is_locking is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000146:1", "DIRECTION", 1)
    assert lock.is_unlocking is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000146:1", "DIRECTION", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000146:1", "ERROR", 2)
    assert lock.is_jammed is True


@pytest.mark.asyncio
async def test_ceiplock(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpLock."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    lock: CeIpLock = cast(
        CeIpLock, await get_hm_custom_entity(central, "VCU9724704", 1)
    )
    assert lock.usage == HmEntityUsage.CE_PRIMARY

    assert lock.is_locked is False
    await lock.lock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=0,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 1)
    assert lock.is_locked is True
    await lock.unlock()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 2)
    assert lock.is_locked is False
    await lock.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU9724704:1",
        paramset_key="VALUES",
        parameter="LOCK_TARGET_LEVEL",
        value=2,
    )

    assert lock.is_locking is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 2)
    assert lock.is_locking is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_locking is False

    assert lock.is_unlocking is False
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 1)
    assert lock.is_unlocking is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "ACTIVITY_STATE", 0)
    assert lock.is_unlocking is False

    assert lock.is_jammed is False
