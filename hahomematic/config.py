"""
Global configuration parameters.
"""
from __future__ import annotations

from hahomematic.const import DEFAULT_INIT_TIMEOUT, DEFAULT_TIMEOUT

BASE_DIR = "hahm/"
CACHE_DIR = f"{BASE_DIR}cache"
DEVICE_DESCRIPTIONS_DIR = f"{BASE_DIR}export_device_descriptions"
PARAMSET_DESCRIPTIONS_DIR = f"{BASE_DIR}export_paramset_descriptions"

CONNECTION_CHECKER_INTERVAL = 30
INIT_TIMEOUT = DEFAULT_INIT_TIMEOUT
TIMEOUT = DEFAULT_TIMEOUT
