"""
Global configuration parameters.
"""
from datetime import timedelta

from hahomematic.const import DEFAULT_INIT_TIMEOUT, DEFAULT_TIMEOUT

CACHE_DIR = None
CONNECTION_CHECKER_INTERVAL = timedelta(seconds=30)
INIT_TIMEOUT = DEFAULT_INIT_TIMEOUT
JSON_EXECUTOR_MAX_WORKERS = 4
PROXY_EXECUTOR_MAX_WORKERS = 1
TIMEOUT = DEFAULT_TIMEOUT
