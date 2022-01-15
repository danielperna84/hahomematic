"""
Constants used by hahomematic.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

DEFAULT_ENCODING = "UTF-8"
MANUFACTURER = "eQ-3"
INIT_DATETIME = datetime.strptime("01.01.1970 00:00:00", "%d.%m.%Y %H:%M:%S")
LOCALHOST = "localhost"
IP_LOCALHOST_V4 = "127.0.0.1"
IP_LOCALHOST_V6 = "::1"
IP_ANY_V4 = "0.0.0.0"
IP_ANY_V6 = "::"
PORT_ANY = 0
IDENTIFIERS_SEPARATOR = "@"

PATH_JSON_RPC = "/api/homematic.cgi"

FILE_DEVICES_RAW = None
FILE_DEVICES = "homematic_devices.json"
FILE_PARAMSETS = "homematic_paramsets.json"
FILE_NAMES = "homematic_names.json"

PARAMSET_MASTER = "MASTER"
PARAMSET_VALUES = "VALUES"

RELEVANT_PARAMSETS = [
    PARAMSET_VALUES,
    # PARAMSET_MASTER,
]

HH_EVENT_DELETE_DEVICES = "deleteDevices"
HH_EVENT_DEVICES_CREATED = "devicesCreated"
HH_EVENT_ERROR = "error"
HH_EVENT_LIST_DEVICES = "listDevices"
HH_EVENT_NEW_DEVICES = "newDevices"
HH_EVENT_RE_ADDED_DEVICE = "readdedDevice"
HH_EVENT_REPLACE_DEVICE = "replaceDevice"
HH_EVENT_UPDATE_DEVICE = "updateDevice"

# When CONFIG_PENDING turns from True to False (ONLY then!) we should re fetch the paramsets.
# However, usually multiple of these events are fired, so we should only
# act on the last one. This also only seems to fire on channel 0.
EVENT_CONFIG_PENDING = "CONFIG_PENDING"
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

CLICK_EVENTS = [
    EVENT_PRESS,
    EVENT_PRESS_SHORT,
    EVENT_PRESS_LONG,
    EVENT_PRESS_CONT,
    EVENT_PRESS_LONG_RELEASE,
    EVENT_PRESS_LONG_START,
]

BUTTON_ACTIONS = ["RESET_MOTION", "RESET_PRESENCE"]

SPECIAL_EVENTS = [
    EVENT_CONFIG_PENDING,
    EVENT_ERROR,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
]

# Parameters within the paramsets for which we create entities.
WHITELIST_PARAMETERS = ["ERROR_JAMMED", "SMOKE_DETECTOR_ALARM_STATUS"]

# Parameters within the paramsets for which we don't create entities.
IGNORED_PARAMETERS = [
    "ACTIVITY_STATE",
    "AES_KEY",
    "BOOST_TIME",
    "BOOT",
    "BURST_LIMIT_WARNING",
    "CLEAR_WINDOW_OPEN_SYMBOL",
    "COMBINED_PARAMETER",
    "DATE_TIME_UNKNOWN",
    "DECISION_VALUE",
    "DEVICE_IN_BOOTLOADER",
    "DEW_POINT_ALARM",
    "EMERGENCY_OPERATION",
    "EXTERNAL_CLOCK",
    "FROST_PROTECTION",
    "HUMIDITY_LIMITER",
    "INCLUSION_UNSUPPORTED_DEVICE",
    "INHIBIT",
    "INSTALL_MODE",
    "LEVEL_COMBINED",
    "LEVEL_REAL",
    "OLD_LEVEL",
    "ON_TIME",
    "PARTY_SET_POINT_TEMPERATURE",
    "PARTY_TIME_END",
    "PARTY_TIME_START",
    "PROCESS",
    "QUICK_VETO_TIME",
    "RAMP_STOP",
    "RELOCK_DELAY",
    "SECTION",
    "SELF_CALIBRATION",
    "SENSOR_ERROR",
    "SET_SYMBOL_FOR_HEATING_PHASE",
    "SMOKE_DETECTOR_COMMAND",
    "STATE_UNCERTAIN",
    "SWITCH_POINT_OCCURED",
    "TEMPERATURE_LIMITER",
    "TEMPERATURE_OUT_OF_RANGE",
    "TIME_OF_OPERATION",
    "UPDATE_PENDING",
    "WOCHENPROGRAMM",
]

# Ignore Parameter that end with
IGNORED_PARAMETERS_WILDCARDS_END = [
    "OVERFLOW",
    "OVERHEAT",
    "OVERRUN",
    "REPORTING",
    "RESULT",
    "STATUS",
    "SUBMIT",
    "WORKING",
]

# Ignore Parameter that start with
IGNORED_PARAMETERS_WILDCARDS_START = [
    "ADJUSTING",
    "ERR_TTM",
    "ERROR",
    "IDENTIFICATION_MODE_KEY_VISUAL",
    "IDENTIFY_",
    "PARTY_START",
    "PARTY_STOP",
    "STATUS_FLAG",
    "WEEK_PROGRAM",
]

ACCEPT_PARAMETER_ONLY_ON_CHANNEL = {"LOWBAT": 0}

HIDDEN_PARAMETERS = [EVENT_UN_REACH, EVENT_STICKY_UN_REACH, EVENT_CONFIG_PENDING]

BACKEND_CCU = "CCU"
BACKEND_HOMEGEAR = "Homegear"
BACKEND_PYDEVCCU = "PyDevCCU"

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
ATTR_IP = "ip"
ATTR_JSON_PORT = "json_port"
ATTR_NAME = "name"
ATTR_PASSWORD = "password"
ATTR_PARAMETER = "parameter"
ATTR_PORT = "port"
ATTR_RESULT = "result"
ATTR_SESSION_ID = "_session_id_"
ATTR_TLS = "tls"
ATTR_TYPE = "type"
ATTR_SUBTYPE = "subtype"
ATTR_USERNAME = "username"
ATTR_VALUE = "value"
ATTR_VERIFY_TLS = "verify_tls"

ATTR_HM_ALARM = "ALARM"
ATTR_HM_ADDRESS = "ADDRESS"
ATTR_HM_CHILDREN = "CHILDREN"
ATTR_HM_DEFAULT = "DEFAULT"
ATTR_HM_FIRMWARE = "FIRMWARE"
ATTR_HM_FLAGS = "FLAGS"
ATTR_HM_OPERATIONS = "OPERATIONS"
ATTR_HM_PARAMSETS = "PARAMSETS"
ATTR_HM_PARENT = "PARENT"
ATTR_HM_TYPE = "TYPE"
ATTR_HM_SUBTYPE = "SUBTYPE"
ATTR_HM_LIST = "LIST"
ATTR_HM_LOGIC = "LOGIC"
ATTR_HM_NAME = "NAME"
ATTR_HM_NUMBER = "NUMBER"
ATTR_HM_UNIT = "UNIT"
ATTR_HM_MAX = "MAX"
ATTR_HM_MIN = "MIN"
# Optional member for TYPE: FLOAT, INTEGER
ATTR_HM_SPECIAL = "SPECIAL"  # Which has the following keys
ATTR_HM_VALUE = "VALUE"  # Float or integer, depending on TYPE
# Members for ENUM
ATTR_HM_VALUE_LIST = "VALUE_LIST"

OPERATION_NONE = 0
OPERATION_READ = 1
OPERATION_WRITE = 2
OPERATION_EVENT = 4

TYPE_FLOAT = "FLOAT"
TYPE_INTEGER = "INTEGER"
TYPE_BOOL = "BOOL"
TYPE_ENUM = "ENUM"
TYPE_STRING = "STRING"
TYPE_ACTION = "ACTION"  # Usually buttons, send Boolean to trigger

FLAG_VISIBLE = 1
FLAG_INTERAL = 2
# FLAG_TRANSFORM = 4 # not used
FLAG_SERVICE = 8
# FLAG_STICKY = 10  # This might be wrong. Documentation says 0x10 # not used

DEFAULT_PASSWORD = None
DEFAULT_USERNAME = "Admin"
DEFAULT_TIMEOUT = 30
DEFAULT_INIT_TIMEOUT = 90
DEFAULT_TLS = False
DEFAULT_VERIFY_TLS = False

HM_ENTITY_UNIT_REPLACE: dict[str, str] = {'"': "", "100%": "%", "% rF": "%"}

# virtual remotes device_types
HM_VIRTUAL_REMOTE_HM = "HM-RCV-50"
HM_VIRTUAL_REMOTE_HMW = "HMW-RCV-50"
HM_VIRTUAL_REMOTE_HMIP = "HmIP-RCV-50"
HM_VIRTUAL_REMOTES = [
    HM_VIRTUAL_REMOTE_HM,
    HM_VIRTUAL_REMOTE_HMW,
    HM_VIRTUAL_REMOTE_HMIP,
]


class HmEntityUsage(Enum):
    """Enum with information about usage in Home Assistant."""

    CE_PRIMARY = "ce_primary"
    CE_SECONDARY = "ce_secondary"
    CE_SENSOR = "ce_sensor"
    ENTITY_NO_CREATE = "entity_no_create"
    ENTITY = "ENTITY"
    EVENT = "event"


class HmPlatform(Enum):
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
    SWITCH = "switch"
    TEXT = "text"

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)


class HmEntityType(Enum):
    """Enum with hahomematic entity types."""

    GENERIC = "generic"
    CUSTOM = "custom"

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)


class HmEventType(Enum):
    """Enum with hahomematic event types."""

    KEYPRESS = "homematic.keypress"
    SPECIAL = "homematic.special"

    def __str__(self) -> str:
        """Return self.value."""
        return str(self.value)


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
    HmPlatform.SWITCH,
]
