"""Tests for climate entities of hahomematic."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from unittest.mock import call

from freezegun import freeze_time
import pytest

from hahomematic.const import EntityUsage, ParamsetKey
from hahomematic.platforms.custom.climate import (
    CeIpThermostat,
    CeRfThermostat,
    CeSimpleRfThermostat,
    HvacAction,
    HvacMode,
    ModeHmIP,
    PresetMode,
)

from tests import const, helper

TEST_DEVICES: dict[str, str] = {
    "VCU1769958": "HmIP-BWTH.json",
    "VCU3609622": "HmIP-eTRV-2.json",
    "INT0000001": "HM-CC-VG-1.json",
    "VCU5778428": "HmIP-HEATING.json",
    "VCU0000054": "HM-CC-TC.json",
    "VCU0000050": "HM-CC-RT-DN.json",
}

# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_cesimplerfthermostat(factory: helper.Factory) -> None:
    """Test CeSimpleRfThermostat."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    climate: CeSimpleRfThermostat = cast(
        CeSimpleRfThermostat, helper.get_prepared_custom_entity(central, "VCU0000054", 1)
    )
    assert climate.usage == EntityUsage.CE_PRIMARY

    assert climate.is_valid is False
    assert climate.state_uncertain is False
    assert climate.temperature_unit == "°C"
    assert climate.min_temp == 6.0
    assert climate.max_temp == 30.0
    assert climate.supports_preset is False
    assert climate.target_temperature_step == 0.5

    assert climate.current_humidity is None
    central.event(const.INTERFACE_ID, "VCU0000054:1", "HUMIDITY", 75)
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    last_call = call.set_value(
        channel_address="VCU0000054:2",
        paramset_key="VALUES",
        parameter="SETPOINT",
        value=12.0,
    )
    assert mock_client.method_calls[-1] == last_call
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    central.event(const.INTERFACE_ID, "VCU0000054:1", "TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HvacMode.HEAT
    assert climate.hvac_modes == (HvacMode.HEAT,)
    assert climate.preset_mode == PresetMode.NONE
    assert climate.preset_modes == (PresetMode.NONE,)
    assert climate.hvac_action is None
    central.event(const.INTERFACE_ID, "VCU0000054:1", "TEMPERATURE", 11.0)

    # No new method call, because called methods has no implementation
    await climate.set_hvac_mode(HvacMode.HEAT)
    assert mock_client.method_calls[-1] == last_call
    await climate.set_preset_mode(PresetMode.NONE)
    assert mock_client.method_calls[-1] == last_call
    await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
    assert mock_client.method_calls[-1] == last_call
    await climate.enable_away_mode_by_calendar(
        start=datetime.now(), end=datetime.now(), away_temperature=17.0
    )
    assert mock_client.method_calls[-1] == last_call
    await climate.disable_away_mode()
    assert mock_client.method_calls[-1] == last_call


@pytest.mark.asyncio
async def test_cerfthermostat(factory: helper.Factory) -> None:
    """Test CeRfThermostat."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    climate: CeRfThermostat = cast(
        CeRfThermostat, helper.get_prepared_custom_entity(central, "VCU0000050", 4)
    )
    assert climate.usage == EntityUsage.CE_PRIMARY
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.supports_preset is True
    assert climate.target_temperature_step == 0.5
    assert climate.preset_mode == PresetMode.NONE
    assert climate.hvac_action is None
    central.event(const.INTERFACE_ID, "VCU0000050:4", "VALVE_STATE", 10)
    assert climate.hvac_action == HvacAction.HEAT
    central.event(const.INTERFACE_ID, "VCU0000050:4", "VALVE_STATE", 0)
    assert climate.hvac_action == HvacAction.IDLE
    assert climate.current_humidity is None
    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="SET_TEMPERATURE",
        value=12.0,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    central.event(const.INTERFACE_ID, "VCU0000050:4", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HvacMode.AUTO
    assert climate.hvac_modes == (HvacMode.AUTO, HvacMode.HEAT, HvacMode.OFF)
    await climate.set_hvac_mode(HvacMode.HEAT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4", paramset_key="VALUES", parameter="MANU_MODE", value=12.0
    )
    central.event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", ModeHmIP.MANU.value)
    assert climate.hvac_mode == HvacMode.HEAT

    await climate.set_hvac_mode(HvacMode.OFF)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU0000050:4",
        paramset_key="VALUES",
        value={"MANU_MODE": 12.0, "SET_TEMPERATURE": 4.5},
    )

    assert climate.hvac_mode == HvacMode.OFF
    assert climate.hvac_action == HvacAction.OFF

    await climate.set_hvac_mode(HvacMode.AUTO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4", paramset_key="VALUES", parameter="AUTO_MODE", value=True
    )
    central.event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 0)
    central.event(const.INTERFACE_ID, "VCU0000050:4", "SET_TEMPERATURE", 24.0)
    assert climate.hvac_mode == HvacMode.AUTO

    assert climate.preset_mode == PresetMode.NONE
    assert climate.preset_modes == (
        PresetMode.BOOST,
        PresetMode.COMFORT,
        PresetMode.ECO,
        PresetMode.NONE,
    )
    await climate.set_preset_mode(PresetMode.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="BOOST_MODE",
        value=True,
    )
    central.event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 3)
    assert climate.preset_mode == PresetMode.BOOST
    central.event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 2)
    assert climate.preset_mode == PresetMode.AWAY
    await climate.set_preset_mode(PresetMode.COMFORT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="COMFORT_MODE",
        value=True,
    )
    await climate.set_preset_mode(PresetMode.ECO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="LOWERING_MODE",
        value=True,
    )

    central.event(const.INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 3)
    call_count = len(mock_client.method_calls)
    await climate.set_preset_mode(PresetMode.BOOST)
    assert call_count == len(mock_client.method_calls)

    await climate.set_hvac_mode(HvacMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_hvac_mode(HvacMode.AUTO)
    assert call_count == len(mock_client.method_calls)

    with freeze_time("2023-03-03 08:00:00"):
        await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="PARTY_MODE_SUBMIT",
        value="17.0,470,03,03,23,720,07,03,23",
    )

    with freeze_time("2023-03-03 08:00:00"):
        await climate.enable_away_mode_by_calendar(
            start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
        )
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="PARTY_MODE_SUBMIT",
        value="17.0,0,01,12,00,0,01,12,24",
    )

    with freeze_time("2023-03-03 08:00:00"):
        await climate.disable_away_mode()
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key=ParamsetKey.VALUES,
        parameter="PARTY_MODE_SUBMIT",
        value="12.0,1260,02,03,23,1320,02,03,23",
    )


@pytest.mark.asyncio
async def test_ceipthermostat(factory: helper.Factory) -> None:
    """Test CeIpThermostat."""
    central, mock_client = await factory.get_default_central(TEST_DEVICES)
    climate: CeIpThermostat = cast(
        CeIpThermostat, helper.get_prepared_custom_entity(central, "VCU1769958", 1)
    )
    assert climate.usage == EntityUsage.CE_PRIMARY
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.supports_preset is True
    assert climate.target_temperature_step == 0.5
    assert climate.hvac_action == HvacAction.IDLE
    central.event(const.INTERFACE_ID, "VCU1769958:9", "STATE", 1)
    assert climate.hvac_action == HvacAction.HEAT
    central.event(const.INTERFACE_ID, "VCU1769958:9", "STATE", 0)
    assert climate.hvac_action == HvacAction.IDLE

    assert climate.current_humidity is None
    central.event(const.INTERFACE_ID, "VCU1769958:1", "HUMIDITY", 75)
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key="VALUES",
        parameter="SET_POINT_TEMPERATURE",
        value=12.0,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    central.event(const.INTERFACE_ID, "VCU1769958:1", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HvacMode.AUTO
    assert climate.hvac_modes == (HvacMode.AUTO, HvacMode.HEAT, HvacMode.OFF)
    assert climate.preset_mode == PresetMode.NONE

    await climate.set_hvac_mode(HvacMode.OFF)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 4.5},
    )
    assert climate.hvac_mode == HvacMode.OFF
    assert climate.hvac_action == HvacAction.OFF

    await climate.set_hvac_mode(HvacMode.HEAT)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={"CONTROL_MODE": 1, "SET_POINT_TEMPERATURE": 5.0},
    )
    central.event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", ModeHmIP.MANU.value)
    assert climate.hvac_mode == HvacMode.HEAT

    assert climate.preset_mode == PresetMode.NONE
    assert climate.preset_modes == (
        PresetMode.BOOST,
        PresetMode.NONE,
    )
    await climate.set_preset_mode(PresetMode.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1", paramset_key="VALUES", parameter="BOOST_MODE", value=True
    )
    central.event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    assert climate.preset_mode == PresetMode.BOOST

    await climate.set_hvac_mode(HvacMode.AUTO)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={"BOOST_MODE": False, "CONTROL_MODE": 0},
    )
    central.event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", ModeHmIP.AUTO.value)
    central.event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    assert climate.hvac_mode == HvacMode.AUTO
    assert climate.preset_modes == (
        PresetMode.BOOST,
        PresetMode.NONE,
        "week_program_1",
        "week_program_2",
        "week_program_3",
        "week_program_4",
        "week_program_5",
        "week_program_6",
    )
    await climate.set_preset_mode(PresetMode.NONE)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1", paramset_key="VALUES", parameter="BOOST_MODE", value=False
    )
    central.event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", ModeHmIP.AWAY.value)
    assert climate.preset_mode == PresetMode.AWAY

    central.event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", ModeHmIP.AUTO.value)
    await climate.set_preset_mode(PresetMode.WEEK_PROGRAM_1)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1", paramset_key="VALUES", parameter="ACTIVE_PROFILE", value=1
    )
    assert climate.preset_mode == PresetMode.WEEK_PROGRAM_1

    with freeze_time("2023-03-03 08:00:00"):
        await climate.enable_away_mode_by_duration(hours=100, away_temperature=17.0)
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={
            "SET_POINT_MODE": 2,
            "SET_POINT_TEMPERATURE": 17.0,
            "PARTY_TIME_START": "2023_03_03 07:50",
            "PARTY_TIME_END": "2023_03_07 12:00",
        },
    )

    await climate.enable_away_mode_by_calendar(
        start=datetime(2000, 12, 1), end=datetime(2024, 12, 1), away_temperature=17.0
    )
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={
            "SET_POINT_MODE": 2,
            "SET_POINT_TEMPERATURE": 17.0,
            "PARTY_TIME_START": "2000_12_01 00:00",
            "PARTY_TIME_END": "2024_12_01 00:00",
        },
    )

    await climate.disable_away_mode()
    assert mock_client.method_calls[-1] == call.put_paramset(
        address="VCU1769958:1",
        paramset_key="VALUES",
        value={
            "SET_POINT_MODE": 2,
            "PARTY_TIME_START": "2000_01_01 00:00",
            "PARTY_TIME_END": "2000_01_01 00:00",
        },
    )

    central.event(const.INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    call_count = len(mock_client.method_calls)
    await climate.set_preset_mode(PresetMode.BOOST)
    assert call_count == len(mock_client.method_calls)

    central.event(const.INTERFACE_ID, "VCU1769958:1", "SET_POINT_TEMPERATURE", 12.0)
    call_count = len(mock_client.method_calls)
    await climate.set_temperature(12.0)
    assert call_count == len(mock_client.method_calls)

    await climate.set_hvac_mode(HvacMode.AUTO)
    call_count = len(mock_client.method_calls)
    await climate.set_hvac_mode(HvacMode.AUTO)
    assert call_count == len(mock_client.method_calls)
