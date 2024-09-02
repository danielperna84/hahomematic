"""Validator functions used within hahomematic."""

from __future__ import annotations

import voluptuous as vol

from hahomematic.const import MAX_WAIT_FOR_CALLBACK
from hahomematic.support import is_address, is_channel_address, is_device_address

channel_no = vol.All(vol.Coerce(int), vol.Range(min=1, max=999))
wait_for = vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_WAIT_FOR_CALLBACK))


def address(value: str) -> str:
    """Validate channel_address."""
    if is_address(address=value):
        return value
    raise vol.Invalid("address is invalid")


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
