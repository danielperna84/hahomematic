"""
Global configuration parameters.
"""
from __future__ import annotations

from hahomematic.const import (
    DEFAULT_CONNECTION_CHECKER_INTERVAL,
    DEFAULT_RECONNECT_WAIT,
    DEFAULT_TIMEOUT,
)

CHECK_INTERVAL = DEFAULT_CONNECTION_CHECKER_INTERVAL * 6
CONNECTION_CHECKER_INTERVAL = DEFAULT_CONNECTION_CHECKER_INTERVAL
RECONNECT_WAIT = DEFAULT_RECONNECT_WAIT
TIMEOUT = DEFAULT_TIMEOUT
