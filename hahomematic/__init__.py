"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
https://github.com/danielperna84/hahomematic
"""
from __future__ import annotations

import logging
import signal
import sys

import hahomematic.data as hm_data

if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
# noinspection PyUnusedLocal
def signal_handler(sig, frame):  # type: ignore[no-untyped-def]
    """Handle signal to shut down central_unit."""
    _LOGGER.info("Got signal: %s. Shutting down central_unit", str(sig))
    for central in hm_data.INSTANCES.values():
        central.stop()


if sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)
