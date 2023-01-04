"""Tests for cover entities of hahomematic."""
from __future__ import annotations

from typing import cast

from conftest import get_hm_custom_entity
import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.cover import CeBlind, CeCover, CeGarage, CeIpBlind

TEST_DEVICES = {
    "VCU8537918": "HmIP-BROLL.json",
    "VCU1223813": "HmIP-FBL.json",
    "VCU0000045": "HM-LC-Bl1-FM.json",
    "VCU6529515": "HmIP-MOD-HO.json",
    "VCU0000145": "HM-LC-JaX.json",
}


@pytest.mark.asyncio
async def test_cecover(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeCover."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeCover = cast(CeCover, await get_hm_custom_entity(central, "VCU8537918", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    await cover.set_cover_position(81)
    assert cover.current_cover_position == 81
    await cover.open_cover()
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert cover.current_cover_position == 0


@pytest.mark.asyncio
async def test_ceblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeBlind."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeBlind = cast(CeBlind, await get_hm_custom_entity(central, "VCU0000145", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 0
    await cover.close_cover()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0


@pytest.mark.asyncio
async def test_ceipblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeIpBlind = cast(
        CeIpBlind, await get_hm_custom_entity(central, "VCU1223813", 4)
    )
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 100
    await cover.close_cover()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0


@pytest.mark.asyncio
async def test_cegarage(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarage."""
    central = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    cover: CeGarage = cast(
        CeGarage, await get_hm_custom_entity(central, "VCU6529515", 1)
    )
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position is None
    await cover.set_cover_position(81)
    central.event(const.LOCAL_INTERFACE_ID, "VCU6529515:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
    await cover.close_cover()
    central.event(const.LOCAL_INTERFACE_ID, "VCU6529515:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0
    await cover.set_cover_position(10)
    central.event(const.LOCAL_INTERFACE_ID, "VCU6529515:1", "DOOR_STATE", 2)
    assert cover.current_cover_position == 10
    await cover.open_cover()
    central.event(const.LOCAL_INTERFACE_ID, "VCU6529515:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
