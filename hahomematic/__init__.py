"""
hahomematic is a Python 3 (>= 3.10) module for Home Assistant.

The lib interacts with HomeMatic and HomematicIP devices.
https://github.com/danielperna84/hahomematic
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys
from typing import Any

import hahomematic.central_unit as hmcu
from hahomematic.decorators import (
    get_public_attributes_for_config_property,
    get_public_attributes_for_value_property,
)

if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
# noinspection PyUnusedLocal
def signal_handler(sig, frame):  # type: ignore[no-untyped-def]
    """Handle signal to shut down central_unit."""
    _LOGGER.info("Got signal: %s. Shutting down central_unit", str(sig))
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    for central in hmcu.CENTRAL_INSTANCES.values():
        asyncio.run_coroutine_threadsafe(central.stop(), asyncio.get_running_loop())


if sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)


class PayloadMixin:
    """Mixin to add payload methods to class."""

    @property
    def config_payload(self) -> dict[str, Any]:
        """Return the config payload."""
        return get_public_attributes_for_config_property(data_object=self)

    @property
    def value_payload(self) -> dict[str, Any]:
        """Return the value payload."""
        return get_public_attributes_for_value_property(data_object=self)
