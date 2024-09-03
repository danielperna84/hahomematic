"""Validator functions used within hahomematic."""

from __future__ import annotations

import voluptuous as vol

from hahomematic.const import MAX_WAIT_FOR_CALLBACK
from hahomematic.support import (
    check_password,
    is_channel_address,
    is_device_address,
    is_hostname,
    is_ipv4_address,
    is_paramset_key,
)

channel_no = vol.All(vol.Coerce(int), vol.Range(min=0, max=999))
positive_int = vol.All(vol.Coerce(int), vol.Range(min=0))
wait_for = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_WAIT_FOR_CALLBACK))


def channel_address(value: str) -> str:
    """Validate channel_address."""
    if is_channel_address(address=value):
        return value
    raise vol.Invalid("channel_address is invalid")


def device_address(value: str) -> str:
    """Validate channel_address."""
    if is_device_address(address=value):
        return value
    raise vol.Invalid("device_address is invalid")


def hostname(value: str) -> str:
    """Validate hostname."""
    if is_hostname(hostname=value):
        return value
    raise vol.Invalid("hostname is invalid")


def ipv4_address(value: str) -> str:
    """Validate ipv4_address."""
    if is_ipv4_address(address=value):
        return value
    raise vol.Invalid("ipv4_address is invalid")


def password(value: str) -> str:
    """Validate password."""
    if check_password(password=value):
        return value
    raise vol.Invalid("password is invalid")


def paramset_key(value: str) -> str:
    """Validate paramset_key."""
    if is_paramset_key(paramset_key=value):
        return value
    raise vol.Invalid("paramset_key is invalid")


address = vol.All(vol.Coerce(str), vol.Any(device_address, channel_address))
host = vol.All(vol.Coerce(str), vol.Any(hostname, ipv4_address))
