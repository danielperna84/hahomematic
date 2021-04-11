"""
hahomematic is a Python 3 (>= 3.6) module for Home Assistant to interact with
HomeMatic and homematic IP devices.
Some other devices (f.ex. Bosch, Intertechno) might be supported as well.
https://github.com/danielperna84/hahomematic
"""

import os
import sys
import json
import logging
import signal

from hahomematic import data, config
from hahomematic.server import Server
from hahomematic.client import Client

if sys.stdout.isatty():
    logging.basicConfig(level=logging.DEBUG)

LOG = logging.getLogger(__name__)

# pylint: disable=unused-argument
def signal_handler(sig, frame):
    """Handle signal to shut down server."""
    LOG.info("Got signal: %s. Shutting down server", str(sig))
    data.SERVER.stop()

if sys.stdout.isatty():
    signal.signal(signal.SIGINT, signal_handler)
