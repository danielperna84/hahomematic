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

from hahomematic import central_unit as hmcu

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
