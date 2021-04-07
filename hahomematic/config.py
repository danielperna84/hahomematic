"""
Global configuration parameters.
"""

from hahomematic.const import DEFAULT_INTERFACE_ID, DEFAULT_TIMEOUT, DEFAULT_INIT_TIMEOUT

INTERFACE_ID = DEFAULT_INTERFACE_ID
TIMEOUT = DEFAULT_TIMEOUT
INIT_TIMEOUT = DEFAULT_INIT_TIMEOUT
FILE_DEVICES = None
FILE_PARAMSETS = None
FILE_NAMES = None

# Signature: f(name, *args)
CALLBACK_SYSTEM = None
# Signature: f(interface_id, address, value_key, value)
CALLBACK_EVENT = None
# Signature: f(entity_id)
CALLBACK_ENTITY_UPDATE = None
