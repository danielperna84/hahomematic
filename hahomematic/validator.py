"""Validator functions used within hahomematic."""

from __future__ import annotations

import voluptuous as vol

from hahomematic.support import is_address, is_channel_address, is_channel_no, is_device_address


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


def channel_no(value: int) -> int:
    """Validate channel_no."""
    if is_channel_no(channel_no=value):
        return value
    raise vol.Invalid("channel_no is invalid")


def device_address(value: str) -> str:
    """Validate channel_address."""
    if is_device_address(address=value):
        return value
    raise vol.Invalid("device_address is invalid")
