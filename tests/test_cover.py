"""Tests for cover entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.cover import (
    GARAGE_DOOR_HO_SECTION_CLOSING,
    GARAGE_DOOR_HO_SECTION_OPENING,
    GARAGE_DOOR_TM_SECTION_CLOSING,
    GARAGE_DOOR_TM_SECTION_OPENING,
    HM_CLOSED,
    HM_OPEN,
    HM_WD_CLOSED,
    CeBlind,
    CeCover,
    CeGarageHO,
    CeGarageTM,
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


@pytest.mark.asyncio
async def test_cecover(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeCover."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeCover = cast(CeCover, await helper.get_custom_entity(central, "VCU8537918", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_CLOSED
    assert cover.is_closed is True
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.is_closed is False
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=1.0,
    )
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU8537918:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_CLOSED,
    )
    assert cover.current_cover_position == 0

    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU8537918:3", "LEVEL", 0.5)
    assert cover.channel_level == 0.5
    assert cover.current_cover_position == 50


@pytest.mark.asyncio
async def test_ceipblind_dr(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind DIN Rail."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, await helper.get_custom_entity(central, "VCU7807849", 2))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_CLOSED
    assert cover.channel_operation_mode == "SHUTTER"
    assert cover.is_closed is True
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU7807849:2",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.is_closed is False
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU7807849:2", paramset_key="VALUES", value={"LEVEL_2": 1.0, "LEVEL": 1.0}
    )
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU7807849:2", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.0}
    )
    assert cover.current_cover_position == 0

    assert cover.is_opening is None
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 1)
    assert cover.is_opening is True
    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "ACTIVITY_STATE", 2)
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU7807849:1", "LEVEL", 0.5)
    assert cover.channel_level == 0.5
    assert cover.current_cover_position == 50


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

    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_WD_CLOSED
    assert cover.is_closed is True
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.is_closed is False

    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_OPEN,
    )
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000350:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_WD_CLOSED,
    )
    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_WD_CLOSED
    assert cover.is_closed is True

    await cover.set_cover_position(1)
    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_CLOSED
    assert cover.is_closed is False

    await cover.set_cover_position(0.0)
    assert cover.current_cover_position == 0
    assert cover.channel_level == HM_WD_CLOSED
    assert cover.is_closed is True


@pytest.mark.asyncio
async def test_ceblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeBlind."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeBlind = cast(CeBlind, await helper.get_custom_entity(central, "VCU0000145", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_OPEN,
    )
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 0
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=HM_CLOSED,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=HM_OPEN,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=0.45,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="LEVEL_SLATS",
        value=HM_CLOSED,
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0

    await cover.stop_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="STOP",
        value=True,
    )
    await cover.stop_cover_tilt()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000145:1",
        paramset_key="VALUES",
        parameter="STOP",
        value=True,
    )


@pytest.mark.asyncio
async def test_ceipblind(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpBlind."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeIpBlind = cast(CeIpBlind, await helper.get_custom_entity(central, "VCU1223813", 4))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1223813:4",
        paramset_key="VALUES",
        parameter="LEVEL",
        value=0.81,
    )
    assert cover.current_cover_position == 81
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1223813:4", paramset_key="VALUES", value={"LEVEL_2": 1.0, "LEVEL": 1.0}
    )
    assert cover.current_cover_position == 100
    assert cover.current_cover_tilt_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1223813:4", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.0}
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0
    await cover.open_cover_tilt()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1223813:4", paramset_key="VALUES", value={"LEVEL_2": 1.0, "LEVEL": 0.0}
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 100
    await cover.set_cover_tilt_position(45)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1223813:4", paramset_key="VALUES", value={"LEVEL_2": 0.45, "LEVEL": 0.0}
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 45
    await cover.close_cover_tilt()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1223813:4", paramset_key="VALUES", value={"LEVEL_2": 0.0, "LEVEL": 0.0}
    )
    assert cover.current_cover_position == 0
    assert cover.current_cover_tilt_position == 0

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL", 0.5)
    assert cover.channel_level == 0.5
    assert cover.current_cover_position == 50

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL_2", 0.8)
    assert cover.channel_tilt_level == 0.8
    assert cover.current_cover_tilt_position == 80

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL", None)
    assert cover.channel_level == HM_CLOSED
    assert cover.current_cover_position == 0

    central.event(const.LOCAL_INTERFACE_ID, "VCU1223813:3", "LEVEL_2", None)
    assert cover.channel_tilt_level == HM_CLOSED
    assert cover.current_cover_tilt_position == 0


@pytest.mark.asyncio
async def test_cegarageho(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarageHO."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeGarageHO = cast(CeGarageHO, await helper.get_custom_entity(central, "VCU3574044", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position is None
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0
    assert cover.is_closed is True
    await cover.set_cover_position(11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 2)
    assert cover.current_cover_position == 10

    await cover.set_cover_position(5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0

    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    await cover.stop_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU3574044:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=2,
    )

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100

    central.event(
        const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", GARAGE_DOOR_HO_SECTION_OPENING
    )
    assert cover.is_opening is True
    central.event(
        const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", GARAGE_DOOR_HO_SECTION_CLOSING
    )
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU3574044:1", "DOOR_STATE", None)
    assert cover.is_closed is None


@pytest.mark.asyncio
async def test_cegaragetm(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeGarageTM."""
    central, mock_client = await central_local_factory.get_default_central(TEST_DEVICES)
    cover: CeGarageTM = cast(CeGarageTM, await helper.get_custom_entity(central, "VCU6166407", 1))
    assert cover.usage == HmEntityUsage.CE_PRIMARY

    assert cover.current_cover_position is None
    await cover.set_cover_position(81)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100
    await cover.close_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0
    assert cover.is_closed is True
    await cover.set_cover_position(11)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=4,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 2)
    assert cover.current_cover_position == 10

    await cover.set_cover_position(5)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=3,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 0)
    assert cover.current_cover_position == 0

    await cover.open_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=1,
    )
    await cover.stop_cover()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU6166407:1",
        paramset_key="VALUES",
        parameter="DOOR_COMMAND",
        value=2,
    )

    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", 1)
    assert cover.current_cover_position == 100

    central.event(
        const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", GARAGE_DOOR_TM_SECTION_OPENING
    )
    assert cover.is_opening is True
    central.event(
        const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", GARAGE_DOOR_TM_SECTION_CLOSING
    )
    assert cover.is_closing is True

    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_opening is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "SECTION", None)
    assert cover.is_closing is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU6166407:1", "DOOR_STATE", None)
    assert cover.is_closed is None
