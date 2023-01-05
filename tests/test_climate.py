"""Tests for climate entities of hahomematic."""
from __future__ import annotations

from typing import cast
from unittest.mock import call

import const
import helper
from helper import get_hm_custom_entity
import pytest

from hahomematic.const import HmEntityUsage
from hahomematic.custom_platforms.climate import (
    CeIpThermostat,
    CeRfThermostat,
    CeSimpleRfThermostat,
    HmHvacMode,
    HmPresetMode,
)

TEST_DEVICES: dict[str, str] = {
    "VCU1769958": "HmIP-BWTH.json",
    "VCU3609622": "HmIP-eTRV-2.json",
    "INT0000001": "HM-CC-VG-1.json",
    "VCU5778428": "HmIP-HEATING.json",
    "VCU0000054": "HM-CC-TC.json",
    "VCU0000050": "HM-CC-RT-DN.json",
}


@pytest.mark.asyncio
async def test_cesimplerfthermostat(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeSimpleRfThermostat."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    climate: CeSimpleRfThermostat = cast(
        CeSimpleRfThermostat, await get_hm_custom_entity(central, "VCU0000054", 1)
    )
    assert climate.usage == HmEntityUsage.CE_PRIMARY
    assert climate.min_temp == 6.0
    assert climate.max_temp == 30.0
    assert climate.target_temperature_step == 0.5

    assert climate.current_humidity is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000054:1", "HUMIDITY", 75)
    assert climate.current_humidity == 75

    assert climate.target_temperature is None
    await climate.set_temperature(12.0)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000054:2",
        paramset_key="VALUES",
        parameter="SETPOINT",
        value=12.0,
    )
    assert climate.target_temperature == 12.0

    assert climate.current_temperature is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000054:1", "TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HmHvacMode.HEAT
    assert climate.hvac_modes == [HmHvacMode.HEAT]
    assert climate.preset_mode == HmPresetMode.NONE
    assert climate.preset_modes == [HmPresetMode.NONE]


@pytest.mark.asyncio
async def test_cerfthermostat(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeRfThermostat."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    climate: CeRfThermostat = cast(
        CeRfThermostat, await get_hm_custom_entity(central, "VCU0000050", 4)
    )
    assert climate.usage == HmEntityUsage.CE_PRIMARY
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.target_temperature_step == 0.5

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
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000050:4", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HmHvacMode.AUTO
    assert climate.hvac_modes == [HmHvacMode.AUTO, HmHvacMode.HEAT, HmHvacMode.OFF]
    await climate.set_hvac_mode(HmHvacMode.HEAT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="MANU_MODE",
        value=12.0,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 1)
    assert climate.hvac_mode == HmHvacMode.HEAT

    assert climate.preset_mode == HmPresetMode.NONE
    assert climate.preset_modes == [
        HmPresetMode.BOOST,
        HmPresetMode.COMFORT,
        HmPresetMode.ECO,
        HmPresetMode.NONE,
    ]
    await climate.set_preset_mode(HmPresetMode.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU0000050:4",
        paramset_key="VALUES",
        parameter="BOOST_MODE",
        value=True,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU0000050:4", "CONTROL_MODE", 3)
    assert climate.preset_mode == HmPresetMode.BOOST


@pytest.mark.asyncio
async def test_ceipthermostat(
    central_local_factory: helper.CentralUnitLocalFactory,
) -> None:
    """Test CeIpThermostat."""
    central, mock_client = await central_local_factory.get_central(TEST_DEVICES)
    assert central
    climate: CeIpThermostat = cast(
        CeIpThermostat, await get_hm_custom_entity(central, "VCU1769958", 1)
    )
    assert climate.usage == HmEntityUsage.CE_PRIMARY
    assert climate.min_temp == 5.0
    assert climate.max_temp == 30.5
    assert climate.target_temperature_step == 0.5

    assert climate.current_humidity is None
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "HUMIDITY", 75)
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
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "ACTUAL_TEMPERATURE", 11.0)
    assert climate.current_temperature == 11.0

    assert climate.hvac_mode == HmHvacMode.AUTO
    assert climate.hvac_modes == [HmHvacMode.AUTO, HmHvacMode.HEAT, HmHvacMode.OFF]
    await climate.set_hvac_mode(HmHvacMode.HEAT)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key="VALUES",
        parameter="SET_POINT_TEMPERATURE",
        value=12.0,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", 1)
    assert climate.hvac_mode == HmHvacMode.HEAT

    assert climate.preset_mode == HmPresetMode.NONE
    assert climate.preset_modes == [
        HmPresetMode.BOOST,
        HmPresetMode.NONE,
    ]
    await climate.set_preset_mode(HmPresetMode.BOOST)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key="VALUES",
        parameter="BOOST_MODE",
        value=True,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    assert climate.preset_mode == HmPresetMode.BOOST

    await climate.set_hvac_mode(HmHvacMode.AUTO)
    assert mock_client.method_calls[-1] == call.set_value(
        channel_address="VCU1769958:1",
        paramset_key="VALUES",
        parameter="BOOST_MODE",
        value=False,
    )
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "SET_POINT_MODE", 0)
    central.event(const.LOCAL_INTERFACE_ID, "VCU1769958:1", "BOOST_MODE", 1)
    assert climate.hvac_mode == HmHvacMode.AUTO
    assert climate.preset_modes == [
        HmPresetMode.BOOST,
        HmPresetMode.NONE,
        "week_program_1",
        "week_program_2",
        "week_program_3",
        "week_program_4",
        "week_program_5",
        "week_program_6",
    ]
