"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
https://github.com/danielperna84/hahomematic
"""

import logging
import signal
import sys

from hahomematic import config
from hahomematic.client import Client
from hahomematic.data import INSTANCES
from hahomematic.server import Server

if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
# noinspection PyUnusedLocal
def signal_handler(sig, frame):
    """Handle signal to shut down server."""
    _LOGGER.info("Got signal: %s. Shutting down server", str(sig))
    for active_server in INSTANCES.values():
        active_server.stop()


if sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)
