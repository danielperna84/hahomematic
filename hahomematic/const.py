"""Constants used by hahomematic."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, IntEnum, StrEnum
from typing import Final

DEFAULT_CONNECTION_CHECKER_INTERVAL: Final = 15  # check if connection is available via rpc ping
DEFAULT_ENCODING: Final = "UTF-8"
DEFAULT_JSON_SESSION_AGE: Final = 90
DEFAULT_PING_PONG_MISMATCH_COUNT: Final = 10
DEFAULT_RECONNECT_WAIT: Final = 120  # wait with reconnect after a first ping was successful
DEFAULT_TIMEOUT: Final = 60  # default timeout for a connection
DEFAULT_TLS: Final = False
DEFAULT_VERIFY_TLS: Final = False

REGA_SCRIPT_FETCH_ALL_DEVICE_DATA: Final = "fetch_all_device_data.fn"
REGA_SCRIPT_GET_SERIAL: Final = "get_serial.fn"
REGA_SCRIPT_PATH: Final = "../rega_scripts"
REGA_SCRIPT_SET_SYSTEM_VARIABLE: Final = "set_system_variable.fn"
REGA_SCRIPT_SYSTEM_VARIABLES_EXT_MARKER: Final = "get_system_variables_ext_marker.fn"

DEFAULT_DEVICE_DESCRIPTIONS_DIR: Final = "export_device_descriptions"
DEFAULT_PARAMSET_DESCRIPTIONS_DIR: Final = "export_paramset_descriptions"

# Password can be empty.
# Allowed characters: A-Z, a-z, 0-9, .!$():;#-
# The CCU WebUI also supports ÄäÖöÜüß, but these characters are not supported by the XmlRPC servers
CCU_PASSWORD_PATTERN: Final = r"[A-Za-z0-9.!$():;#-]{0,}"

IDENTIFIER_SEPARATOR: Final = "@"
INIT_DATETIME: Final = datetime.strptime("01.01.1970 00:00:00", "%d.%m.%Y %H:%M:%S")
IP_ANY_V4: Final = "0.0.0.0"
PORT_ANY: Final = 0

PATH_JSON_RPC: Final = "/api/homematic.cgi"

HOMEGEAR_SERIAL = "Homegear_SN0815"

PROGRAM_ADDRESS: Final = "program"
SYSVAR_ADDRESS: Final = "sysvar"

CONF_PASSWORD: Final = "password"
CONF_USERNAME: Final = "username"

EVENT_ADDRESS: Final = "address"
EVENT_INSTANCE_NAME: Final = "instance_name"
EVENT_AVAILABLE: Final = "available"
EVENT_CHANNEL_NO: Final = "channel_no"
EVENT_DATA: Final = "data"
EVENT_DEVICE_TYPE: Final = "device_type"
EVENT_INTERFACE_ID: Final = "interface_id"
EVENT_PARAMETER: Final = "parameter"
EVENT_SECONDS_SINCE_LAST_EVENT: Final = "seconds_since_last_event"
EVENT_TYPE: Final = "type"
EVENT_VALUE: Final = "value"

FILE_DEVICES: Final = "homematic_devices.json"
FILE_PARAMSETS: Final = "homematic_paramsets.json"

MAX_CACHE_AGE: Final = 60

DEVICE_ERROR_EVENTS: Final[tuple[str, ...]] = ("ERROR", "SENSOR_ERROR")

NO_CACHE_ENTRY: Final = "NO_CACHE_ENTRY"

# virtual remotes device_types
VIRTUAL_REMOTE_TYPES: Final[tuple[str, ...]] = (
    "HM-RCV-50",
    "HMW-RCV-50",
    "HmIP-RCV-50",
)

VIRTUAL_REMOTE_ADDRESSES: Final[tuple[str, ...]] = (
    "BidCoS-RF",
    "HMW-RCV-50",
    "HmIP-RCV-1",
)


class Backend(StrEnum):
    """Enum with supported hahomematic backends."""

    CCU = "CCU"
    HOMEGEAR = "Homegear"
    PYDEVCCU = "PyDevCCU"


class CallSource(StrEnum):
    """Enum with sources for calls."""

    HA_INIT: Final = "ha_init"
    HM_INIT: Final = "hm_init"
    MANUAL_OR_SCHEDULED: Final = "manual_or_scheduled"


class DataOperationResult(Enum):
    """Enum with data operation results."""

    LOAD_FAIL: Final = 0
    LOAD_SUCCESS: Final = 1
    SAVE_FAIL: Final = 10
    SAVE_SUCCESS: Final = 11
    NO_LOAD: Final = 20
    NO_SAVE: Final = 21


class Description(StrEnum):
    """Enum with homematic device/paramset description attributes."""

    ADDRESS = "ADDRESS"
    AVAILABLE_FIRMWARE = "AVAILABLE_FIRMWARE"
    CHILDREN = "CHILDREN"
    DEFAULT = "DEFAULT"
    FIRMWARE = "FIRMWARE"
    FIRMWARE_UPDATABLE = "UPDATABLE"
    FIRMWARE_UPDATE_STATE = "FIRMWARE_UPDATE_STATE"
    FLAGS = "FLAGS"
    MAX = "MAX"
    MIN = "MIN"
    NAME = "NAME"
    OPERATIONS = "OPERATIONS"
    PARAMSETS = "PARAMSETS"
    PARENT = "PARENT"
    PARENT_TYPE = "PARENT_TYPE"
    SPECIAL = "SPECIAL"  # Which has the following keys
    SUBTYPE = "SUBTYPE"
    TYPE = "TYPE"
    UNIT = "UNIT"
    VALUE_LIST = "VALUE_LIST"


class DeviceFirmwareState(StrEnum):
    """Enum with homematic device firmware states."""

    UP_TO_DATE: Final = "UP_TO_DATE"
    LIVE_UP_TO_DATE: Final = "LIVE_UP_TO_DATE"
    NEW_FIRMWARE_AVAILABLE: Final = "NEW_FIRMWARE_AVAILABLE"
    LIVE_NEW_FIRMWARE_AVAILABLE: Final = "LIVE_NEW_FIRMWARE_AVAILABLE"
    DELIVER_FIRMWARE_IMAGE: Final = "DELIVER_FIRMWARE_IMAGE"
    LIVE_DELIVER_FIRMWARE_IMAGE: Final = "LIVE_DELIVER_FIRMWARE_IMAGE"
    READY_FOR_UPDATE: Final = "READY_FOR_UPDATE"
    DO_UPDATE_PENDING: Final = "DO_UPDATE_PENDING"
    PERFORMING_UPDATE: Final = "PERFORMING_UPDATE"


class EntityUsage(StrEnum):
    """Enum with information about usage in Home Assistant."""

    CE_PRIMARY: Final = "ce_primary"
    CE_SECONDARY: Final = "ce_secondary"
    CE_VISIBLE: Final = "ce_visible"
    ENTITY: Final = "entity"
    EVENT: Final = "event"
    NO_CREATE: Final = "entity_no_create"


class EventType(StrEnum):
    """Enum with hahomematic event types."""

    DEVICE_AVAILABILITY: Final = "homematic.device_availability"
    DEVICE_ERROR: Final = "homematic.device_error"
    IMPULSE: Final = "homematic.impulse"
    INTERFACE: Final = "homematic.interface"
    KEYPRESS: Final = "homematic.keypress"


class Flag(IntEnum):
    """Enum with homematic flags."""

    VISIBLE = 1
    INTERNAL = 2
    TRANSFORM = 4  # not used
    SERVICE = 8
    STICKY = 10  # This might be wrong. Documentation says 0x10 # not used


class ForcedDeviceAvailability(StrEnum):
    """Enum with hahomematic event types."""

    FORCE_FALSE: Final = "forced_not_available"
    FORCE_TRUE: Final = "forced_available"
    NOT_SET: Final = "not_set"


class Manufacturer(StrEnum):
    """Enum with hahomematic system events."""

    EQ3 = "eQ-3"
    HB = "Homebrew"
    MOEHLENHOFF = "Möhlenhoff"


class Operations(IntEnum):
    """Enum with homematic operations."""

    NONE = 0  # not used
    READ = 1
    WRITE = 2
    EVENT = 4


class Parameter(StrEnum):
    """Enum with homematic params."""

    ACTIVITY_STATE = "ACTIVITY_STATE"
    CHANNEL_OPERATION_MODE = "CHANNEL_OPERATION_MODE"
    CONFIG_PENDING = "CONFIG_PENDING"
    CURRENT_ILLUMINATION = "CURRENT_ILLUMINATION"
    DEVICE_OPERATION_MODE = "DEVICE_OPERATION_MODE"
    DIRECTION = "DIRECTION"
    ERROR = "ERROR"
    ERROR_JAMMED = "ERROR_JAMMED"
    LED_STATUS = "LED_STATUS"
    LEVEL = "LEVEL"
    LOWBAT = "LOWBAT"
    LOW_BAT = "LOW_BAT"
    OPERATING_VOLTAGE = "OPERATING_VOLTAGE"
    PONG = "PONG"
    PRESS = "PRESS"
    PRESS_CONT = "PRESS_CONT"
    PRESS_LOCK = "PRESS_LOCK"
    PRESS_LONG = "PRESS_LONG"
    PRESS_LONG_RELEASE = "PRESS_LONG_RELEASE"
    PRESS_LONG_START = "PRESS_LONG_START"
    PRESS_SHORT = "PRESS_SHORT"
    PRESS_UNLOCK = "PRESS_UNLOCK"
    SECTION = "SECTION"
    SEQUENCE_OK = "SEQUENCE_OK"
    SMOKE_DETECTOR_ALARM_STATUS = "SMOKE_DETECTOR_ALARM_STATUS"
    STATUS = "STATUS"
    STICKY_UN_REACH = "STICKY_UNREACH"
    TEMPERATURE_MAXIMUM = "TEMPERATURE_MAXIMUM"
    TEMPERATURE_MINIMUM = "TEMPERATURE_MINIMUM"
    UN_REACH = "UNREACH"
    UPDATE_PENDING = "UPDATE_PENDING"
    VALVE_STATE = "VALVE_STATE"
    WORKING = "WORKING"


class ParamsetKey(StrEnum):
    """Enum with paramset keys."""

    MASTER = "MASTER"
    VALUES = "VALUES"


class HmPlatform(StrEnum):
    """Enum with platforms relevant for Home Assistant."""

    ACTION: Final = "action"
    BINARY_SENSOR: Final = "binary_sensor"
    BUTTON: Final = "button"
    CLIMATE: Final = "climate"
    COVER: Final = "cover"
    EVENT: Final = "event"
    HUB_BINARY_SENSOR: Final = "hub_binary_sensor"
    HUB_BUTTON: Final = "hub_button"
    HUB_NUMBER: Final = "hub_number"
    HUB_SELECT: Final = "hub_select"
    HUB_SENSOR: Final = "hub_sensor"
    HUB_SWITCH: Final = "hub_switch"
    HUB_TEXT: Final = "hub_text"
    LIGHT: Final = "light"
    LOCK: Final = "lock"
    NUMBER: Final = "number"
    SELECT: Final = "select"
    SENSOR: Final = "sensor"
    SIREN: Final = "siren"
    SWITCH: Final = "switch"
    TEXT: Final = "text"
    UPDATE: Final = "update"


class ProductGroup(StrEnum):
    """Enum with homematic product groups."""

    UNKNOWN: Final = "unknown"
    HMIPW: Final = "HmIP-Wired"
    HMIP: Final = "HmIP-RF"
    HMW: Final = "BidCos-Wired"
    HM: Final = "BidCos-RF"
    VIRTUAL: Final = "VirtualDevices"


class InterfaceName(StrEnum):
    """Enum with homematic interface names."""

    BIDCOS_RF = "BidCos-RF"
    BIDCOS_WIRED = "BidCos-Wired"
    HMIP_RF = "HmIP-RF"
    VIRTUAL_DEVICES = "VirtualDevices"


class InterfaceEventType(StrEnum):
    """Enum with hahomematic event types."""

    CALLBACK: Final = "callback"
    PINGPONG: Final = "pingpong"
    PROXY: Final = "proxy"


class ProxyInitState(Enum):
    """Enum with proxy handling results."""

    INIT_FAILED: Final = 0
    INIT_SUCCESS: Final = 1
    DE_INIT_FAILED: Final = 4
    DE_INIT_SUCCESS: Final = 8
    DE_INIT_SKIPPED: Final = 16


class SystemEvent(StrEnum):
    """Enum with hahomematic system events."""

    DELETE_DEVICES = "deleteDevices"
    DEVICES_CREATED = "devicesCreated"
    ERROR = "error"
    HUB_REFRESHED = "hubEntityRefreshed"
    LIST_DEVICES = "listDevices"
    NEW_DEVICES = "newDevices"
    REPLACE_DEVICE = "replaceDevice"
    RE_ADDED_DEVICE = "readdedDevice"
    UPDATE_DEVICE = "updateDevice"


class SysvarType(StrEnum):
    """Enum for homematic sysvar types."""

    ALARM = "ALARM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    LIST = "LIST"
    LOGIC = "LOGIC"
    NUMBER = "NUMBER"
    STRING = "STRING"


class ParameterType(StrEnum):
    """Enum for homematic parameter types."""

    ACTION = "ACTION"  # Usually buttons, send Boolean to trigger
    BOOL = "BOOL"
    ENUM = "ENUM"
    FLOAT = "FLOAT"
    INTEGER = "INTEGER"
    STRING = "STRING"


PLATFORMS: Final[tuple[HmPlatform, ...]] = (
    HmPlatform.BINARY_SENSOR,
    HmPlatform.BUTTON,
    HmPlatform.CLIMATE,
    HmPlatform.COVER,
    HmPlatform.EVENT,
    HmPlatform.LIGHT,
    HmPlatform.LOCK,
    HmPlatform.NUMBER,
    HmPlatform.SELECT,
    HmPlatform.SENSOR,
    HmPlatform.SIREN,
    HmPlatform.SWITCH,
    HmPlatform.TEXT,
    HmPlatform.UPDATE,
)

HUB_PLATFORMS: Final[tuple[HmPlatform, ...]] = (
    HmPlatform.HUB_BINARY_SENSOR,
    HmPlatform.HUB_BUTTON,
    HmPlatform.HUB_NUMBER,
    HmPlatform.HUB_SELECT,
    HmPlatform.HUB_SENSOR,
    HmPlatform.HUB_SWITCH,
    HmPlatform.HUB_TEXT,
)

CLICK_EVENTS: Final[tuple[str, ...]] = (
    Parameter.PRESS,
    Parameter.PRESS_CONT,
    Parameter.PRESS_LOCK,
    Parameter.PRESS_LONG,
    Parameter.PRESS_LONG_RELEASE,
    Parameter.PRESS_LONG_START,
    Parameter.PRESS_SHORT,
    Parameter.PRESS_UNLOCK,
)

ENTITY_EVENTS: Final = (
    EventType.IMPULSE,
    EventType.KEYPRESS,
)

IMPULSE_EVENTS: Final[tuple[str, ...]] = (Parameter.SEQUENCE_OK,)

KEY_CHANNEL_OPERATION_MODE_VISIBILITY: Final[dict[str, tuple[str, ...]]] = {
    "STATE": ("BINARY_BEHAVIOR",),
    Parameter.PRESS_LONG: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_LONG_RELEASE: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_LONG_START: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
    Parameter.PRESS_SHORT: ("KEY_BEHAVIOR", "SWITCH_BEHAVIOR"),
}

RELEVANT_INIT_PARAMETERS: Final[tuple[str, ...]] = (
    Parameter.CONFIG_PENDING,
    Parameter.STICKY_UN_REACH,
    Parameter.UN_REACH,
)


@dataclass(slots=True)
class HubData:
    """Dataclass for hub entities."""

    name: str


@dataclass(slots=True)
class ProgramData(HubData):
    """Dataclass for programs."""

    pid: str
    is_active: bool
    is_internal: bool
    last_execute_time: str


@dataclass(slots=True)
class SystemVariableData(HubData):
    """Dataclass for system variables."""

    value: bool | float | int | str | None
    data_type: SysvarType | None = None
    unit: str | None = None
    value_list: list[str] | None = None
    max_value: float | int | None = None
    min_value: float | int | None = None
    extended_sysvar: bool = False


@dataclass(slots=True)
class SystemInformation:
    """System information of the backend."""

    available_interfaces: list[str] = field(default_factory=list)
    auth_enabled: bool | None = None
    https_redirect_enabled: bool | None = None
    serial: str | None = None
