"""Tests for button entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_custom_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.lock import CeIpLock, CeRfLock

TEST_DEVICES = {
    "VCU9724704": "HmIP-DLD.json",
    "VCU0000146": "HM-Sec-Key.json",
}


@pytest.mark.asyncio
async def test_cerflock(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeRfLock."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    lock: CeRfLock = cast(
        CeRfLock, await get_hm_custom_entity(central, "VCU0000146", 1)
    )
    assert lock.usage == HmEntityUsage.CE_PRIMARY

    assert lock.is_locked is True
    await lock.unlock()
    assert lock.is_locked is False
    await lock.lock()
    assert lock.is_locked is True
    await lock.open()

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
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    lock: CeIpLock = cast(
        CeIpLock, await get_hm_custom_entity(central, "VCU9724704", 1)
    )
    assert lock.usage == HmEntityUsage.CE_PRIMARY

    assert lock.is_locked is False
    await lock.lock()
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 1)
    assert lock.is_locked is True
    await lock.unlock()
    central.event(const.LOCAL_INTERFACE_ID, "VCU9724704:1", "LOCK_STATE", 2)
    assert lock.is_locked is False
    await lock.open()

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
