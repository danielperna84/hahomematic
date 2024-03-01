"""Tests for json rpc client of hahomematic."""

from __future__ import annotations

import json

import orjson
import pytest

SUCCESS = '{"HmIP-RF.0001D3C99C3C93%3A0.CONFIG_PENDING":false,\r\n"VirtualDevices.INT0000001%3A1.SET_POINT_TEMPERATURE":4.500000,\r\n"VirtualDevices.INT0000001%3A1.SWITCH_POINT_OCCURED":false,\r\n"VirtualDevices.INT0000001%3A1.VALVE_STATE":4,\r\n"VirtualDevices.INT0000001%3A1.WINDOW_STATE":0,\r\n"HmIP-RF.001F9A49942EC2%3A0.CARRIER_SENSE_LEVEL":10.000000,\r\n"HmIP-RF.0003D7098F5176%3A0.UNREACH":false,\r\n"BidCos-RF.OEQ1860891%3A0.UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A0.STICKY_UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A1.INHIBIT":false,\r\n"HmIP-RF.000A570998B3FB%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A570998B3FB%3A0.UPDATE_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.UPDATE_PENDING":false,\r\n"BidCos-RF.NEQ1636407%3A1.STATE":0,\r\n"BidCos-RF.NEQ1636407%3A2.STATE":false,\r\n"BidCos-RF.NEQ1636407%3A2.INHIBIT":false,\r\n"CUxD.CUX2800001%3A12.TS":"0"}'
FAILURE = '{"HmIP-RF.0001D3C99C3C93%3A0.CONFIG_PENDING":false,\r\n"VirtualDevices.INT0000001%3A1.SET_POINT_TEMPERATURE":4.500000,\r\n"VirtualDevices.INT0000001%3A1.SWITCH_POINT_OCCURED":false,\r\n"VirtualDevices.INT0000001%3A1.VALVE_STATE":4,\r\n"VirtualDevices.INT0000001%3A1.WINDOW_STATE":0,\r\n"HmIP-RF.001F9A49942EC2%3A0.CARRIER_SENSE_LEVEL":10.000000,\r\n"HmIP-RF.0003D7098F5176%3A0.UNREACH":false,\r\n,\r\n,\r\n"BidCos-RF.OEQ1860891%3A0.UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A0.STICKY_UNREACH":true,\r\n"BidCos-RF.OEQ1860891%3A1.INHIBIT":false,\r\n"HmIP-RF.000A570998B3FB%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A570998B3FB%3A0.UPDATE_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.CONFIG_PENDING":false,\r\n"HmIP-RF.000A5A4991BDDC%3A0.UPDATE_PENDING":false,\r\n"BidCos-RF.NEQ1636407%3A1.STATE":0,\r\n"BidCos-RF.NEQ1636407%3A2.STATE":false,\r\n"BidCos-RF.NEQ1636407%3A2.INHIBIT":false,\r\n"CUxD.CUX2800001%3A12.TS":"0"}'


def test_convert_to_json_success() -> None:
    """Test if convert to json is successful."""
    assert orjson.loads(SUCCESS)


def test_convert_to_json_fails() -> None:
    """Test if convert to json is successful."""
    with pytest.raises(json.JSONDecodeError):
        orjson.loads(FAILURE)
