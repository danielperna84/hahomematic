"""Tests for cover entities of hahomematic."""

from __future__ import annotations

from typing import cast
from unittest.mock import call

import pytest

from hahomematic.const import EntityUsage
from hahomematic.platforms.custom.cover import (
    _CLOSED_LEVEL,
    _OPEN_LEVEL,
    _WD_CLOSED_LEVEL,
    CeBlind,
    CeCover,
    CeGarage,
    CeIpBlind,
    CeWindowDrive,
    GarageDoorActivity,
)

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU0000045": "HM-LC-Bl1-FM.json",
    "VCU0000145": "HM-LC-JaX.json",
    "VCU0000350": "HM-Sec-Win.json",
    "VCU1223813": "HmIP-FBL.json",
    "VCU3560967": "HmIP-HDM1.json",
    "VCU3574044": "HmIP-MOD-HO.json",
    "VCU6166407": "HmIP-MOD-TM.json",
    "VCU7807849": "HmIPW-DRBL4.json",
    "VCU8537918": "HmIP-BROLL.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_cecover(factory: helper.Factory) -> None:
    """Test CeCover."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeCover = cast(CeCover, helper.get_prepared_custom_entity(central, "VCU8537918", 4))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == _CLOSED_LEVEL
    assert cover.is_closed is True
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_position == 81
    assert cover.is_closed is False
    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=1.0,
    )
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=_CLOSED_LEVEL,
    )
    assert cover.current_position == 0

    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True
    central.event(const.INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 0)

    central.event(const.INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50

    central.event(const.INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.0)
    call_count = len(mock_client.method_calls)
    await cover.close()
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU8537918:3", "LEVEL", 1.0)
    call_count = len(mock_client.method_calls)
    await cover.open()
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.4)
    call_count = len(mock_client.method_calls)
    await cover.set_position(position=40)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipblind_dr(factory: helper.Factory) -> None:
    """Test CeIpBlind DIN Rail."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, helper.get_prepared_custom_entity(central, "VCU7807849", 2))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == _CLOSED_LEVEL
    assert cover.channel_operation_mode == "SHUTTER"
    assert cover.is_closed is True
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=81",
    )
    central.event(const.INTERFACE_ID, "VCU7807849:1", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.is_closed is False
    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=100",
    )
    central.event(const.INTERFACE_ID, "VCU7807849:1", "LEVEL", _OPEN_LEVEL)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.INTERFACE_ID, "VCU7807849:1", "LEVEL", _CLOSED_LEVEL)
    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True

    central.event(const.INTERFACE_ID, "VCU7807849:1", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50


@pytest.mark.asyncio
async def test_cewindowdrive(factory: helper.Factory) -> None:
    """Test CeWindowDrive."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeWindowDrive = cast(
        CeWindowDrive, helper.get_prepared_custom_entity(central, "VCU0000350", 1)
    )
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == _WD_CLOSED_LEVEL
    assert cover.is_closed is True
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_position == 81
    assert cover.is_closed is False

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=_OPEN_LEVEL,
    )
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=_WD_CLOSED_LEVEL,
    )
    assert cover.current_position == 0
    assert cover._channel_level == _WD_CLOSED_LEVEL
    assert cover.is_closed is True

    await cover.set_position(position=1)
    assert cover.current_position == 1
    assert cover._channel_level == _CLOSED_LEVEL
    assert cover.is_closed is False

    await cover.set_position(position=0.0)
    assert cover.current_position == 0
    assert cover._channel_level == _WD_CLOSED_LEVEL
    assert cover.is_closed is True


@pytest.mark.asyncio
async def test_ceblind(factory: helper.Factory) -> None:
    """Test CeBlind."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeBlind = cast(CeBlind, helper.get_prepared_custom_entity(central, "VCU0000145", 1))
    assert cover.usage == EntityUsage.CE_PRIMARY
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0xa2,0x00",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.current_tilt_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0xc8,0x00",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL", _OPEN_LEVEL)
    assert cover.current_position == 100
    assert cover.current_tilt_position == 0

    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x00,0x00",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL", _CLOSED_LEVEL)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.open_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x00,0xc8",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _OPEN_LEVEL)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 100

    await cover.set_position(tilt_position=45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x00,0x5a",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.45)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 45

    await cover.close_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x00,0x00",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _CLOSED_LEVEL)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_position(position=10, tilt_position=20)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x14,0x28",
    )
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL", 0.1)
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.2)
    assert cover.current_position == 10
    assert cover.current_tilt_position == 20

    await cover.stop()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="STOP",
        value=True,
    )
    await cover.stop_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="STOP",
        value=True,
    )

    await cover.open_tilt()
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _OPEN_LEVEL)
    call_count = len(mock_client.method_calls)
    await cover.open_tilt()
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _OPEN_LEVEL)
    assert call_count == len(mock_client.method_calls)

    await cover.close_tilt()
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _CLOSED_LEVEL)
    call_count = len(mock_client.method_calls)
    await cover.close_tilt()
    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", _CLOSED_LEVEL)
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.4)
    call_count = len(mock_client.method_calls)
    await cover.set_position(tilt_position=40)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipblind(factory: helper.Factory) -> None:
    """Test CeIpBlind."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, helper.get_prepared_custom_entity(central, "VCU1223813", 4))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover.current_tilt_position == 0
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=81",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.current_tilt_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=100",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 1.0)
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL", 1.0)
    assert cover.current_position == 100
    assert cover.current_tilt_position == 100

    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.0)
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.open_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=0",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 1.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 100

    await cover.set_position(tilt_position=45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=45,L=0",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.45)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 45

    await cover.close_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.0)
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_position(position=10, tilt_position=20)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=20,L=10",
    )
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.1)
    central.event(const.INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.2)
    assert cover.current_position == 10
    assert cover.current_tilt_position == 20

    central.event(const.INTERFACE_ID, "VCU1223813:3", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50

    central.event(const.INTERFACE_ID, "VCU1223813:3", "LEVEL_2", 0.8)
    assert cover._channel_tilt_level == 0.8
    assert cover.current_tilt_position == 80

    central.event(const.INTERFACE_ID, "VCU1223813:3", "LEVEL", _CLOSED_LEVEL)
    assert cover._channel_level == _CLOSED_LEVEL
    assert cover.current_position == 0

    central.event(const.INTERFACE_ID, "VCU1223813:3", "LEVEL_2", _CLOSED_LEVEL)
    assert cover._channel_tilt_level == _CLOSED_LEVEL
    assert cover.current_tilt_position == 0

    central.event(const.INTERFACE_ID, "VCU1223813:3", "ACTIVITY_STATE", 1)
    assert cover.is_opening

    central.event(const.INTERFACE_ID, "VCU1223813:3", "ACTIVITY_STATE", 2)
    assert cover.is_closing

    central.event(const.INTERFACE_ID, "VCU1223813:3", "ACTIVITY_STATE", 3)
    assert cover.is_opening is False
    assert cover.is_closing is False

    await cover.stop()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4", paramset_key="VALUES", parameter="STOP", value=True
    )


@pytest.mark.asyncio
async def test_ceipblind_hdm(factory: helper.Factory) -> None:
    """Test CeIpBlind HDM."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, helper.get_prepared_custom_entity(central, "VCU3560967", 1))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover.current_tilt_position == 0
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.81}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.current_tilt_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 1.0, "LEVEL": 1.0}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 1.0)
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL", 1.0)
    assert cover.current_position == 100
    assert cover.current_tilt_position == 100

    await cover.close()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.0}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 0.0)
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.open_tilt()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 1.0, "LEVEL": 0.0}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 1.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 100

    await cover.set_position(tilt_position=45)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 0.45, "LEVEL": 0.0}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 0.45)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 45

    await cover.close_tilt()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.0}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 0.0)
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_position(position=10, tilt_position=20)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU3560967:1", paramset_key="VALUES", value={"LEVEL_2": 0.2, "LEVEL": 0.1}
    )
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL", 0.1)
    central.event(const.INTERFACE_ID, "VCU3560967:1", "LEVEL_2", 0.2)
    assert cover.current_position == 10
    assert cover.current_tilt_position == 20

    central.event(const.INTERFACE_ID, "VCU3560967:1", "ACTIVITY_STATE", 1)
    assert cover.is_opening

    central.event(const.INTERFACE_ID, "VCU3560967:1", "ACTIVITY_STATE", 2)
    assert cover.is_closing

    central.event(const.INTERFACE_ID, "VCU3560967:1", "ACTIVITY_STATE", 3)
    assert cover.is_opening is False
    assert cover.is_closing is False

    await cover.stop()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3560967:1", paramset_key="VALUES", parameter="STOP", value=True
    )


@pytest.mark.asyncio
async def test_cegarageho(factory: helper.Factory) -> None:
    """Test CeGarageHO."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeGarage = cast(CeGarage, helper.get_prepared_custom_entity(central, "VCU3574044", 1))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position is None
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_position == 0
    assert cover.is_closed is True
    await cover.set_position(position=11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    assert cover.current_position == 10

    await cover.set_position(position=5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    await cover.stop()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=2,
    )

    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_position == 100

    central.event(const.INTERFACE_ID, "VCU3574044:1", "SECTION", GarageDoorActivity.OPENING.value)
    assert cover.is_opening is True
    central.event(const.INTERFACE_ID, "VCU3574044:1", "SECTION", GarageDoorActivity.CLOSING.value)
    assert cover.is_closing is True

    central.event(const.INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", None)
    assert cover.is_closed is None

    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    call_count = len(mock_client.method_calls)
    await cover.close()
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    call_count = len(mock_client.method_calls)
    await cover.open()
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    call_count = len(mock_client.method_calls)
    await cover.vent()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_cegaragetm(factory: helper.Factory) -> None:
    """Test CeGarageTM."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    cover: CeGarage = cast(CeGarage, helper.get_prepared_custom_entity(central, "VCU6166407", 1))
    assert cover.usage == EntityUsage.CE_PRIMARY

    assert cover.current_position is None
    await cover.set_position(position=81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
    assert cover.current_position == 0
    assert cover.is_closed is True
    await cover.set_position(position=11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 2)
    assert cover.current_position == 10

    await cover.set_position(position=5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
    assert cover.current_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    await cover.stop()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=2,
    )

    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_position == 100

    central.event(const.INTERFACE_ID, "VCU6166407:1", "SECTION", GarageDoorActivity.OPENING)
    assert cover.is_opening is True
    central.event(const.INTERFACE_ID, "VCU6166407:1", "SECTION", GarageDoorActivity.CLOSING)
    assert cover.is_closing is True

    central.event(const.INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", None)
    assert cover.is_closed is None
