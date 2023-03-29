"""Tests for cover entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.platforms.custom.cover import (
    GARAGE_DOOR_SECTION_CLOSING,
    GARAGE_DOOR_SECTION_OPENING,
    HM_CLOSED,
    HM_OPEN,
    HM_WD_CLOSED,
    CeBlind,
    CeCover,
    CeGarage,
    CeIpBlind,
    CeWindowDrive,
)

TEST_DEVICES: dict[str, str] = {
    "VCU8537918": "HmIP-BROLL.json",
    "VCU7807849": "HmIPW-DRBL4.json",
    "VCU1223813": "HmIP-FBL.json",
    "VCU0000045": "HM-LC-Bl1-FM.json",
    "VCU3574044": "HmIP-MOD-HO.json",
    "VCU6166407": "HmIP-MOD-TM.json",
    "VCU0000145": "HM-LC-JaX.json",
    "VCU0000350": "HM-Sec-Win.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_cecover(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeCover."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeCover = cast(CeCover, await helper.get_custom_entity(central, "VCU8537918", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == HM_CLOSED
    assert cover.is_closed is True
    await cover.set_position(81)
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
        value=HM_CLOSED,
    )
    assert cover.current_position == 0

    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 0)

    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50

    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.0)
    call_count = len(mock_client.method_calls)
    await cover.close()
    assert call_count == len(mock_client.method_calls)

    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "LEVEL", 1.0)
    call_count = len(mock_client.method_calls)
    await cover.open()
    assert call_count == len(mock_client.method_calls)

    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.4)
    call_count = len(mock_client.method_calls)
    await cover.set_position(40)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipblind_dr(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind DIN Rail."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, await helper.get_custom_entity(central, "VCU7807849", 2))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == HM_CLOSED
    assert cover.channel_operation_mode == "SHUTTER"
    assert cover.is_closed is True
    await cover.set_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=81",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.is_closed is False
    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=100",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "LEVEL", HM_OPEN)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "LEVEL", HM_CLOSED)
    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50


@pytest.mark.asyncio
async def test_cewindowdrive(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeWindowDrive."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeWindowDrive = cast(
        CeWindowDrive, await helper.get_custom_entity(central, "VCU0000350", 1)
    )
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover._channel_level == HM_WD_CLOSED
    assert cover.is_closed is True
    await cover.set_position(81)
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
        value=HM_OPEN,
    )
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_WD_CLOSED,
    )
    assert cover.current_position == 0
    assert cover._channel_level == HM_WD_CLOSED
    assert cover.is_closed is True

    await cover.set_position(1)
    assert cover.current_position == 1
    assert cover._channel_level == HM_CLOSED
    assert cover.is_closed is False

    await cover.set_position(0.0)
    assert cover.current_position == 0
    assert cover._channel_level == HM_WD_CLOSED
    assert cover.is_closed is True


@pytest.mark.asyncio
async def test_ceblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeBlind."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeBlind = cast(CeBlind, await helper.get_custom_entity(central, "VCU0000145", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0xa2,0x0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.current_tilt_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0xc8,0x0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL", HM_OPEN)
    assert cover.current_position == 100
    assert cover.current_tilt_position == 0

    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x0,0x0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL", HM_CLOSED)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.open_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x0,0xc8",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_OPEN)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 100

    await cover.set_tilt_position(45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x0,0x5a",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.45)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 45

    await cover.close_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x0,0x0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_CLOSED)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_combined_position(position=10, tilt_position=20)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_COMBINED",
        value="0x14,0x28",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL", 0.1)
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.2)
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
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_OPEN)
    call_count = len(mock_client.method_calls)
    await cover.open_tilt()
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_OPEN)
    assert call_count == len(mock_client.method_calls)

    await cover.close_tilt()
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_CLOSED)
    call_count = len(mock_client.method_calls)
    await cover.close_tilt()
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", HM_CLOSED)
    assert call_count == len(mock_client.method_calls)

    central.event(const.LOCAL_INTERFACE_ID, "VCU0000145:1", "LEVEL_SLATS", 0.4)
    call_count = len(mock_client.method_calls)
    await cover.set_tilt_position(40)
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_ceipblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, await helper.get_custom_entity(central, "VCU1223813", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position == 0
    assert cover.current_tilt_position == 0
    await cover.set_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=81",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.81)
    assert cover.current_position == 81
    assert cover.current_tilt_position == 0

    await cover.open()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=100",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 1.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL", 1.0)
    assert cover.current_position == 100
    assert cover.current_tilt_position == 100

    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.open_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=100,L=0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 1.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 100

    await cover.set_tilt_position(45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=45,L=0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.45)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 45

    await cover.close_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=0,L=0",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.0)
    assert cover.current_position == 0
    assert cover.current_tilt_position == 0

    await cover.set_combined_position(position=10, tilt_position=20)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="COMBINED_PARAMETER",
        value="L2=20,L=10",
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL", 0.1)
    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:4", "LEVEL_2", 0.2)
    assert cover.current_position == 10
    assert cover.current_tilt_position == 20

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL", 0.5)
    assert cover._channel_level == 0.5
    assert cover.current_position == 50

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL_2", 0.8)
    assert cover._channel_tilt_level == 0.8
    assert cover.current_tilt_position == 80

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL", HM_CLOSED)
    assert cover._channel_level == HM_CLOSED
    assert cover.current_position == 0

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL_2", HM_CLOSED)
    assert cover._channel_tilt_level == HM_CLOSED
    assert cover.current_tilt_position == 0


@pytest.mark.asyncio
async def test_cegarageho(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarageHO."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeGarage = cast(CeGarage, await helper.get_custom_entity(central, "VCU3574044", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position is None
    await cover.set_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_position == 0
    assert cover.is_closed is True
    await cover.set_position(11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    assert cover.current_position == 10

    await cover.set_position(5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
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

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_position == 100

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", GARAGE_DOOR_SECTION_OPENING)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", GARAGE_DOOR_SECTION_CLOSING)
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", None)
    assert cover.is_closed is None

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    call_count = len(mock_client.method_calls)
    await cover.close()
    assert call_count == len(mock_client.method_calls)

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    call_count = len(mock_client.method_calls)
    await cover.open()
    assert call_count == len(mock_client.method_calls)

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    call_count = len(mock_client.method_calls)
    await cover.vent()
    assert call_count == len(mock_client.method_calls)


@pytest.mark.asyncio
async def test_cegaragetm(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarageTM."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeGarage = cast(CeGarage, await helper.get_custom_entity(central, "VCU6166407", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_position is None
    await cover.set_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_position == 100
    await cover.close()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
    assert cover.current_position == 0
    assert cover.is_closed is True
    await cover.set_position(11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 2)
    assert cover.current_position == 10

    await cover.set_position(5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
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

    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_position == 100

    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", GARAGE_DOOR_SECTION_OPENING)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", GARAGE_DOOR_SECTION_CLOSING)
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", None)
    assert cover.is_closed is None
