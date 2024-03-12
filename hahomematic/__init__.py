"""
hahomematic is a Python 3 (>= 3.11) module for Home Assistant.

The lib interacts with HomeMatic and HomematicIP devices.
https://github.com/danielperna84/hahomematic
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import threading
from typing import Final

from hahomematic import central as hmcu

if sys.stdout.isatty():
    logging.basicConfig(level=logging.INFO)

_LOGGER: Final = logging.getLogger(__name__)


# pylint: disable=unused-argument
# noinspection PyUnusedLocal
def signal_handler(sig, frame):  # type: ignore[no-untyped-def]
    """Handle signal to shut down central."""
    _LOGGER.info("Got signal: %s. Shutting down central", str(sig))
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    for central in hmcu.CENTRAL_INSTANCES.values():
        asyncio.run_coroutine_threadsafe(central.stop(), asyncio.get_running_loop())


if threading.current_thread() is threading.main_thread() and sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)
