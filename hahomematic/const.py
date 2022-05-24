""" Constants used by hahomematic. """
from __future__ import annotations

from datetime import datetime

from hahomematic.backport import StrEnum

DEFAULT_ENCODING = "UTF-8"
MANUFACTURER = "eQ-3"
INIT_DATETIME = datetime.strptime("01.01.1970 00:00:00", "%d.%m.%Y %H:%M:%S")
IP_LOCALHOST_V4 = "127.0.0.1"
IP_LOCALHOST_V6 = "::1"
IP_ANY_V4 = "0.0.0.0"
IP_ANY_V6 = "::"
PORT_ANY = 0
IDENTIFIERS_SEPARATOR = "@"

PATH_JSON_RPC = "/api/homematic.cgi"

FILE_DEVICES = "homematic_devices.json"
FILE_PARAMSETS = "homematic_paramsets.json"
FILE_CUSTOM_UN_IGNORE_PARAMETERS = "unignore"

PARAMSET_KEY_MASTER = "MASTER"
PARAMSET_KEY_VALUES = "VALUES"

HH_EVENT_DELETE_DEVICES = "deleteDevices"
HH_EVENT_DEVICES_CREATED = "devicesCreated"
HH_EVENT_ERROR = "error"
HH_EVENT_HUB_CREATED = "hubCreated"
HH_EVENT_LIST_DEVICES = "listDevices"
HH_EVENT_NEW_DEVICES = "newDevices"
HH_EVENT_RE_ADDED_DEVICE = "readdedDevice"
HH_EVENT_REPLACE_DEVICE = "replaceDevice"
HH_EVENT_UPDATE_DEVICE = "updateDevice"

# When CONFIG_PENDING turns from True to False (ONLY then!) we should re fetch the paramsets.
# However, usually multiple of these events are fired, so we should only
# act on the last one. This also only seems to fire on channel 0.
EVENT_CONFIG_PENDING = "CONFIG_PENDING"
EVENT_UPDATE_PENDING = "UPDATE_PENDING"
EVENT_ERROR = "ERROR"

# Only available on CCU
EVENT_PONG = "PONG"
EVENT_PRESS = "PRESS"
EVENT_PRESS_SHORT = "PRESS_SHORT"
EVENT_PRESS_LONG = "PRESS_LONG"
EVENT_PRESS_CONT = "PRESS_CONT"
EVENT_PRESS_LONG_RELEASE = "PRESS_LONG_RELEASE"
EVENT_PRESS_LONG_START = "PRESS_LONG_START"
EVENT_STICKY_UN_REACH = "STICKY_UNREACH"
EVENT_UN_REACH = "UNREACH"

PARAM_CHANNEL_OPERATION_MODE = "CHANNEL_OPERATION_MODE"

CLICK_EVENTS: set[str] = {
    EVENT_PRESS,
    EVENT_PRESS_SHORT,
    EVENT_PRESS_LONG,
    EVENT_PRESS_CONT,
    EVENT_PRESS_LONG_RELEASE,
    EVENT_PRESS_LONG_START,
}

BUTTON_ACTIONS: set[str] = {"RESET_MOTION", "RESET_PRESENCE"}

BACKEND_CCU = "CCU"
BACKEND_HOMEGEAR = "Homegear"
BACKEND_PYDEVCCU = "PyDevCCU"

SYSVAR_ADDRESS = "sysvar"
HUB_ADDRESS = "hub"

HM_ARG_ON_TIME = "on_time"

PROXY_INIT_FAILED = 0
PROXY_INIT_SUCCESS = 1
PROXY_DE_INIT_FAILED = 4
PROXY_DE_INIT_SUCCESS = 8
PROXY_DE_INIT_SKIPPED = 16

DATA_LOAD_SUCCESS = 10
DATA_LOAD_FAIL = 100
DATA_NO_LOAD = 99
DATA_SAVE_SUCCESS = 10
DATA_SAVE_FAIL = 100
DATA_NO_SAVE = 99

ATTR_ADDRESS = "address"
ATTR_CALLBACK_HOST = "callback_host"
ATTR_CALLBACK_PORT = "callback_port"
ATTR_CHANNELS = "channels"
ATTR_ENTITY_TYPE = "entity_type"
ATTR_ERROR = "error"
ATTR_HOST = "host"
ATTR_INTERFACE = "interface"
ATTR_INTERFACE_ID = "interface_id"
ATTR_ID = "id"
ATTR_IP = "ip"
ATTR_JSON_PORT = "json_port"
ATTR_NAME = "name"
ATTR_PASSWORD = "password"
ATTR_PARAMETER = "parameter"
ATTR_PARAMSET_KEY = "paramsetKey"
ATTR_PORT = "port"
ATTR_RESULT = "result"
ATTR_SESSION_ID = "_session_id_"
ATTR_TLS = "tls"
ATTR_TYPE = "type"
ATTR_FUNCTION = "function"
ATTR_SUBTYPE = "subtype"
ATTR_USERNAME = "username"
ATTR_VALUE = "value"
ATTR_VALUE_KEY = "valueKey"
ATTR_VERIFY_TLS = "verify_tls"

SYSVAR_IS_INTERNAL = "isInternal"
SYSVAR_MAX_VALUE = "maxValue"
SYSVAR_MIN_VALUE = "minValue"
SYSVAR_NAME = "name"
SYSVAR_TYPE = "type"
SYSVAR_UNIT = "unit"
SYSVAR_VALUE = "value"
SYSVAR_VALUE_LIST = "valueList"

SYSVAR_TYPE_ALARM = "ALARM"
SYSVAR_TYPE_LOGIC = "LOGIC"
SYSVAR_TYPE_LIST = "LIST"
SYSVAR_TYPE_NUMBER = "NUMBER"

ATTR_HM_ADDRESS = "ADDRESS"
ATTR_HM_CHILDREN = "CHILDREN"
ATTR_HM_DEFAULT = "DEFAULT"
ATTR_HM_FIRMWARE = "FIRMWARE"
ATTR_HM_FLAGS = "FLAGS"
ATTR_HM_OPERATIONS = "OPERATIONS"
ATTR_HM_PARAMSETS = "PARAMSETS"
ATTR_HM_PARENT = "PARENT"
ATTR_HM_PARENT_TYPE = "PARENT_TYPE"
ATTR_HM_TYPE = "TYPE"
ATTR_HM_SUBTYPE = "SUBTYPE"
ATTR_HM_NAME = "NAME"
ATTR_HM_UNIT = "UNIT"
ATTR_HM_MAX = "MAX"
ATTR_HM_MIN = "MIN"
# Optional member for TYPE: FLOAT, INTEGER
ATTR_HM_SPECIAL = "SPECIAL"  # Which has the following keys
ATTR_HM_VALUE = "VALUE"  # Float or integer, depending on TYPE
# Members for ENUM
ATTR_HM_VALUE_LIST = "VALUE_LIST"

REGA_SCRIPT_PATH = "rega_scripts"
REGA_SCRIPT_FETCH_ALL_DEVICE_DATA = "fetch_all_device_data.fn"
REGA_SCRIPT_GET_SERIAL = "get_serial.fn"
REGA_SCRIPT_SET_SYSTEM_VARIABLE = "set_system_variable.fn"

OPERATION_NONE = 0
OPERATION_READ = 1
OPERATION_WRITE = 2
OPERATION_EVENT = 4

TYPE_ACTION = "ACTION"  # Usually buttons, send Boolean to trigger
TYPE_BOOL = "BOOL"
TYPE_ENUM = "ENUM"
TYPE_FLOAT = "FLOAT"
TYPE_INTEGER = "INTEGER"
TYPE_STRING = "STRING"

FLAG_VISIBLE = 1
FLAG_INTERAL = 2
# FLAG_TRANSFORM = 4 # not used
FLAG_SERVICE = 8
# FLAG_STICKY = 10  # This might be wrong. Documentation says 0x10 # not used

IF_VIRTUAL_DEVICES_NAME = "VirtualDevices"
IF_VIRTUAL_DEVICES_PORT = 9292
IF_VIRTUAL_DEVICES_TLS_PORT = 49292
IF_VIRTUAL_DEVICES_PATH = "/groups"
IF_HMIP_RF_NAME = "HmIP-RF"
IF_HMIP_RF_PORT = 2010
IF_HMIP_RF_TLS_PORT = 42010
IF_BIDCOS_WIRED_NAME = "BidCos-Wired"
IF_BIDCOS_WIRED_PORT = 2000
IF_BIDCOS_WIRED_TLS_PORT = 42000
IF_BIDCOS_RF_NAME = "BidCos-RF"
IF_BIDCOS_RF_PORT = 2001
IF_BIDCOS_RF_TLS_PORT = 42001

IF_NAMES = [
    IF_VIRTUAL_DEVICES_NAME,
    IF_HMIP_RF_NAME,
    IF_BIDCOS_WIRED_NAME,
    IF_BIDCOS_RF_NAME,
]
IF_PRIMARY = [IF_HMIP_RF_NAME, IF_BIDCOS_RF_NAME]

IF_DEFAULT_ALLOCATION = {
    IF_VIRTUAL_DEVICES_PORT: IF_VIRTUAL_DEVICES_NAME,
    IF_VIRTUAL_DEVICES_TLS_PORT: IF_VIRTUAL_DEVICES_NAME,
    IF_HMIP_RF_PORT: IF_HMIP_RF_NAME,
    IF_HMIP_RF_TLS_PORT: IF_HMIP_RF_NAME,
    IF_BIDCOS_WIRED_PORT: IF_BIDCOS_WIRED_NAME,
    IF_BIDCOS_WIRED_TLS_PORT: IF_BIDCOS_WIRED_NAME,
    IF_BIDCOS_RF_PORT: IF_BIDCOS_RF_NAME,
    IF_BIDCOS_RF_TLS_PORT: IF_BIDCOS_RF_NAME,
}

DEFAULT_TLS = False
DEFAULT_VERIFY_TLS = False
# default timeout for a connection
DEFAULT_TIMEOUT = 60
# check if connection is available via rpc ping every:
DEFAULT_CONNECTION_CHECKER_INTERVAL = 30
# wait with reconnect after a first ping was successful
DEFAULT_RECONNECT_WAIT = 120

HM_ENTITY_UNIT_REPLACE: dict[str, str] = {
    '"': "",
    "100%": "%",
    "% rF": "%",
    "degree": "°C",
}

# virtual remotes device_types
HM_VIRTUAL_REMOTE_HM = "HM-RCV-50"
HM_VIRTUAL_REMOTE_HMW = "HMW-RCV-50"
HM_VIRTUAL_REMOTE_HMIP = "HmIP-RCV-50"
HM_VIRTUAL_REMOTES = [
    HM_VIRTUAL_REMOTE_HM,
    HM_VIRTUAL_REMOTE_HMW,
    HM_VIRTUAL_REMOTE_HMIP,
]

PARAMETER_FRIENDLY_NAME: dict[str, str] = {}


class HmEntityUsage(StrEnum):
    """Enum with information about usage in Home Assistant."""

    CE_PRIMARY = "ce_primary"
    CE_SECONDARY = "ce_secondary"
    CE_SENSOR = "ce_sensor"
    ENTITY_NO_CREATE = "entity_no_create"
    ENTITY = "ENTITY"
    EVENT = "event"


class HmPlatform(StrEnum):
    """Enum with platforms relevant for Home Assistant."""

    ACTION = "action"
    BINARY_SENSOR = "binary_sensor"
    BUTTON = "button"
    CLIMATE = "climate"
    COVER = "cover"
    EVENT = "event"
    HUB_SENSOR = "hub_sensor"
    HUB_BINARY_SENSOR = "hub_binary_sensor"
    LIGHT = "light"
    LOCK = "lock"
    NUMBER = "number"
    SELECT = "select"
    SENSOR = "sensor"
    SIREN = "siren"
    SWITCH = "switch"
    TEXT = "text"


class HmEntityType(StrEnum):
    """Enum with hahomematic entity types."""

    GENERIC = "generic"
    CUSTOM = "custom"


class HmEventType(StrEnum):
    """Enum with hahomematic event types."""

    KEYPRESS = "homematic.keypress"
    DEVICE = "homematic.device"
    INTERFACE = "homematic.interface"


class HmInterfaceEventType(StrEnum):
    """Enum with hahomematic event types."""

    PROXY = "proxy"
    CALLBACK = "callback"


AVAILABLE_HM_PLATFORMS = [
    HmPlatform.BINARY_SENSOR,
    HmPlatform.BUTTON,
    HmPlatform.CLIMATE,
    HmPlatform.COVER,
    HmPlatform.LIGHT,
    HmPlatform.LOCK,
    HmPlatform.NUMBER,
    HmPlatform.SELECT,
    HmPlatform.SENSOR,
    HmPlatform.SIREN,
    HmPlatform.SWITCH,
]
