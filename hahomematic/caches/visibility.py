"""Module about parameter visibility within hahomematic."""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
import logging
import os
from typing import Any, Final

from hahomematic import central as hmcu, support as hms
from hahomematic.const import CLICK_EVENTS, DEFAULT_ENCODING, Parameter, ParamsetKey
from hahomematic.platforms.custom.definition import get_required_parameters
from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)

_FILE_CUSTOM_UN_IGNORE_PARAMETERS: Final = "unignore"


# Define which additional parameters from MASTER paramset should be created as entity.
# By default these are also on the _HIDDEN_PARAMETERS, which prevents these entities
# from being display by default. Usually these enties are used within custom entities,
# and not for general display.
# {device_type: (channel_no, parameter)}
_RELEVANT_MASTER_PARAMSETS_BY_DEVICE: Final[
    Mapping[str, tuple[tuple[int, ...], tuple[Parameter, ...]]]
] = {
    "HmIP-DRBLI4": (
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 17, 21),
        (Parameter.CHANNEL_OPERATION_MODE,),
    ),
    "HmIP-DRDI3": ((1, 2, 3), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-DRSI1": ((1,), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-DRSI4": ((1, 2, 3, 4), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-DSD-PCB": ((1,), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-FCI1": ((1,), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-FCI6": (tuple(range(1, 7)), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-FSI16": ((1,), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-MIO16-PCB": ((13, 14, 15, 16), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-MOD-RC8": (tuple(range(1, 9)), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIP-RGBW": ((0,), (Parameter.DEVICE_OPERATION_MODE,)),
    "HmIPW-DRBL4": ((1, 5, 9, 13), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIPW-DRI16": (tuple(range(1, 17)), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIPW-DRI32": (tuple(range(1, 33)), (Parameter.CHANNEL_OPERATION_MODE,)),
    "HmIPW-FIO6": (tuple(range(1, 7)), (Parameter.CHANNEL_OPERATION_MODE,)),
    "ALPHA-IP-RBG": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HM-CC-RT-DN": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HM-CC-VG-1": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIP-BWTH": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIP-HEATING": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIP-STH": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIP-WTH": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIP-eTRV": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIPW-STH": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
    "HmIPW-WTH": ((1,), (Parameter.TEMPERATURE_MAXIMUM, Parameter.TEMPERATURE_MINIMUM)),
}

# Some parameters are marked as INTERNAL in the paramset and not considered by default,
# but some are required and should be added here.
ALLOWED_INTERNAL_PARAMETERS: Final[tuple[Parameter, ...]] = (Parameter.DIRECTION,)

# Ignore events for some devices
_IGNORE_DEVICES_FOR_ENTITY_EVENTS: Final[Mapping[str, tuple[Parameter, ...]]] = {
    "HmIP-PS": CLICK_EVENTS,
}

# Entities that will be created, but should be hidden.
_HIDDEN_PARAMETERS: Final[tuple[Parameter, ...]] = (
    Parameter.ACTIVITY_STATE,
    Parameter.CHANNEL_OPERATION_MODE,
    Parameter.CONFIG_PENDING,
    Parameter.DIRECTION,
    Parameter.ERROR,
    Parameter.SECTION,
    Parameter.STICKY_UN_REACH,
    Parameter.TEMPERATURE_MAXIMUM,
    Parameter.TEMPERATURE_MINIMUM,
    Parameter.UN_REACH,
    Parameter.UPDATE_PENDING,
    Parameter.WORKING,
)

# Parameters within the VALUES paramset for which we don't create entities.
_IGNORED_PARAMETERS: Final[tuple[str, ...]] = (
    "ACCESS_AUTHORIZATION",
    "ACOUSTIC_NOTIFICATION_SELECTION",
    "ADAPTION_DRIVE",
    "AES_KEY",
    "ALARM_COUNT",
    "ALL_LEDS",
    "ARROW_DOWN",
    "ARROW_UP",
    "BACKLIGHT",
    "BEEP",
    "BELL",
    "BLIND",
    "BOOST_STATE",
    "BOOST_TIME",
    "BOOT",
    "BULB",
    "CLEAR_ERROR",
    "CLEAR_WINDOW_OPEN_SYMBOL",
    "CLOCK",
    "CONTROL_DIFFERENTIAL_TEMPERATURE",
    "DATE_TIME_UNKNOWN",
    "DECISION_VALUE",
    "DEVICE_IN_BOOTLOADER",
    "DISPLAY_DATA_ALIGNMENT",
    "DISPLAY_DATA_BACKGROUND_COLOR",
    "DISPLAY_DATA_COMMIT",
    "DISPLAY_DATA_ICON",
    "DISPLAY_DATA_ID",
    "DISPLAY_DATA_ID",
    "DISPLAY_DATA_STRING",
    "DISPLAY_DATA_TEXT_COLOR",
    "DOOR",
    "EXTERNAL_CLOCK",
    "FROST_PROTECTION",
    "HUMIDITY_LIMITER",
    "IDENTIFICATION_MODE_KEY_VISUAL",
    "IDENTIFICATION_MODE_LCD_BACKLIGHT",
    "INCLUSION_UNSUPPORTED_DEVICE",
    "INHIBIT",
    "INSTALL_MODE",
    "INTERVAL",
    "LEVEL_REAL",
    "OLD_LEVEL",
    "OVERFLOW",
    "OVERRUN",
    "PARTY_SET_POINT_TEMPERATURE",
    "PARTY_TEMPERATURE",
    "PARTY_TIME_END",
    "PARTY_TIME_START",
    "PHONE",
    "PROCESS",
    "QUICK_VETO_TIME",
    "RAMP_STOP",
    "RELOCK_DELAY",
    "SCENE",
    "SELF_CALIBRATION",
    "SERVICE_COUNT",
    "SET_SYMBOL_FOR_HEATING_PHASE",
    "SHADING_SPEED",
    "SHEV_POS",
    "SPEED",
    "STATE_UNCERTAIN",
    "SUBMIT",
    "SWITCH_POINT_OCCURED",
    "TEMPERATURE_LIMITER",
    "TEMPERATURE_OUT_OF_RANGE",
    "TEXT",
    "TIME_OF_OPERATION",
    "USER_COLOR",
    "USER_PROGRAM",
    "VALVE_ADAPTION",
    "WINDOW",
    "WIN_RELEASE",
    "WIN_RELEASE_ACT",
)

# Ignore Parameter that end with
_IGNORED_PARAMETERS_WILDCARDS_END: Final[tuple[str, ...]] = (
    "_OVERFLOW",
    "_OVERRUN",
    "_REPORTING",
    "_RESULT",
    "_STATUS",
    "_SUBMIT",
)

# Ignore Parameter that start with
_IGNORED_PARAMETERS_WILDCARDS_START: Final[tuple[str, ...]] = (
    "ADJUSTING_",
    "ERR_TTM_",
    "HANDLE_",
    "IDENTIFY_",
    "PARTY_START_",
    "PARTY_STOP_",
    "STATUS_FLAG_",
    "WEEK_PROGRAM_",
)


# Parameters within the paramsets for which we create entities.
_UN_IGNORE_PARAMETERS_BY_DEVICE: Final[Mapping[str, tuple[Parameter, ...]]] = {
    "HmIP-DLD": (Parameter.ERROR_JAMMED,),
    "HmIP-SWSD": (Parameter.SMOKE_DETECTOR_ALARM_STATUS,),
    "HM-OU-LED16": (Parameter.LED_STATUS,),
    "HM-Sec-Win": (Parameter.DIRECTION, Parameter.WORKING, Parameter.ERROR, Parameter.STATUS),
    "HM-Sec-Key": (Parameter.DIRECTION, Parameter.ERROR),
    "HmIP-PCBS-BAT": (
        Parameter.OPERATING_VOLTAGE,
        Parameter.LOW_BAT,
    ),  # To override ignore for HmIP-PCBS
}

# Parameters by device within the VALUES paramset for which we don't create entities.
_IGNORE_PARAMETERS_BY_DEVICE: Final[Mapping[Parameter, tuple[str, ...]]] = {
    Parameter.CURRENT_ILLUMINATION: (
        "HmIP-SMI",
        "HmIP-SMO",
        "HmIP-SPI",
    ),
    Parameter.LOWBAT: (
        "HM-LC-Sw1-DR",
        "HM-LC-Sw1-FM",
        "HM-LC-Sw1-PCB",
        "HM-LC-Sw1-Pl",
        "HM-LC-Sw1-Pl-DN-R1",
        "HM-LC-Sw1PBU-FM",
        "HM-LC-Sw2-FM",
        "HM-LC-Sw4-DR",
        "HM-SwI-3-FM",
    ),
    Parameter.LOW_BAT: ("HmIP-BWTH", "HmIP-PCBS"),
    Parameter.OPERATING_VOLTAGE: (
        "ELV-SH-BS2",
        "HmIP-BDT",
        "HmIP-BROLL",
        "HmIP-BS2",
        "HmIP-BSL",
        "HmIP-BSM",
        "HmIP-BWTH",
        "HmIP-DR",
        "HmIP-FDT",
        "HmIP-FROLL",
        "HmIP-FSM",
        "HmIP-MOD-OC8",
        "HmIP-PCBS",
        "HmIP-PDT",
        "HmIP-PMFS",
        "HmIP-PS",
        "HmIP-SFD",
    ),
    Parameter.VALVE_STATE: ("HmIPW-FALMOT-C12", "HmIP-FALMOT-C12"),
}

# Some devices have parameters on multiple channels,
# but we want to use it only from a certain channel.
_ACCEPT_PARAMETER_ONLY_ON_CHANNEL: Final[Mapping[str, int]] = {Parameter.LOWBAT: 0}


class ParameterVisibilityCache:
    """Cache for parameter visibility."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
    ) -> None:
        """Init the parameter visibility cache."""
        self._central = central
        self._storage_folder: Final = central.config.storage_folder
        self._required_parameters: Final = get_required_parameters()
        self._raw_un_ignore_list: Final[set[str]] = set(central.config.un_ignore_list or set())
        # paramset_key, parameter
        self._un_ignore_parameters_general: Final[Mapping[str, set[str]]] = {
            ParamsetKey.MASTER: set(),
            ParamsetKey.VALUES: set(),
        }
        self._ignore_parameters_by_device_lower: Final[dict[str, tuple[str, ...]]] = {
            parameter: tuple(device_type.lower() for device_type in device_types)
            for parameter, device_types in _IGNORE_PARAMETERS_BY_DEVICE.items()
        }

        self._ignore_devices_for_entity_events_lower: Final[dict[str, tuple[str, ...]]] = {
            device_type.lower(): tuple(event for event in events)
            for device_type, events in _IGNORE_DEVICES_FOR_ENTITY_EVENTS.items()
        }

        self._un_ignore_parameters_by_device_lower: Final[dict[str, tuple[str, ...]]] = {
            device_type.lower(): parameters
            for device_type, parameters in _UN_IGNORE_PARAMETERS_BY_DEVICE.items()
        }

        # device_type, channel_no, paramset_key, set[parameter]
        self._un_ignore_parameters_by_device_paramset_key: Final[
            dict[str, dict[int | None, dict[str, set[str]]]]
        ] = {}

        # unignore from custom unignore files
        # device_type, channel_no, paramset_key, parameter
        self._custom_un_ignore_parameters_by_device_paramset_key: Final[
            dict[str, dict[int | None, dict[str, set[str]]]]
        ] = {}

        # device_type, channel_no
        self._relevant_master_paramsets_by_device: Final[dict[str, set[int | None]]] = {}
        self._init()

    def _init(self) -> None:
        """Process cache initialisation."""
        for (
            device_type,
            channels_parameter,
        ) in _RELEVANT_MASTER_PARAMSETS_BY_DEVICE.items():
            device_type_l = device_type.lower()
            channel_nos, parameters = channels_parameter
            if device_type_l not in self._relevant_master_paramsets_by_device:
                self._relevant_master_paramsets_by_device[device_type_l] = set()
            if device_type_l not in self._un_ignore_parameters_by_device_paramset_key:
                self._un_ignore_parameters_by_device_paramset_key[device_type_l] = {}
            for channel_no in channel_nos:
                self._relevant_master_paramsets_by_device[device_type_l].add(channel_no)
                if (
                    channel_no
                    not in self._un_ignore_parameters_by_device_paramset_key[device_type_l]
                ):
                    self._un_ignore_parameters_by_device_paramset_key[device_type_l][
                        channel_no
                    ] = {ParamsetKey.MASTER: set()}
                for parameter in parameters:
                    self._un_ignore_parameters_by_device_paramset_key[device_type_l][channel_no][
                        ParamsetKey.MASTER
                    ].add(parameter)

    def get_un_ignore_parameters(
        self, device_type: str, channel_no: int | None
    ) -> Mapping[str, tuple[str, ...]]:
        """Return un_ignore_parameters."""
        device_type_l = device_type.lower()
        un_ignore_parameters: dict[str, set[str]] = {}
        if device_type_l is not None and channel_no is not None:
            un_ignore_parameters = self._custom_un_ignore_parameters_by_device_paramset_key.get(
                device_type_l, {}
            ).get(channel_no, {})
        for (
            paramset_key,
            un_ignore_params,
        ) in self._un_ignore_parameters_general.items():
            if paramset_key not in un_ignore_parameters:
                un_ignore_parameters[paramset_key] = set()
            un_ignore_parameters[paramset_key].update(un_ignore_params)

        return {
            paramset_key: tuple(parameters)
            for paramset_key, parameters in un_ignore_parameters.items()
        }

    @lru_cache(maxsize=4096)
    def parameter_is_ignored(
        self,
        device_type: str,
        channel_no: int | None,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Check if parameter can be ignored."""
        device_type_l = device_type.lower()

        if paramset_key == ParamsetKey.VALUES:
            if self.parameter_is_un_ignored(
                device_type=device_type,
                channel_no=channel_no,
                paramset_key=paramset_key,
                parameter=parameter,
            ):
                return False

            if (
                (
                    (
                        parameter in _IGNORED_PARAMETERS
                        or parameter.endswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_END))
                        or parameter.startswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_START))
                    )
                    and parameter not in self._required_parameters
                )
                or hms.element_matches_key(
                    search_elements=self._ignore_parameters_by_device_lower.get(parameter, []),
                    compare_with=device_type_l,
                )
                or hms.element_matches_key(
                    search_elements=self._ignore_devices_for_entity_events_lower,
                    compare_with=parameter,
                    search_key=device_type_l,
                    do_wildcard_search=False,
                )
            ):
                return True

            if (
                accept_channel := _ACCEPT_PARAMETER_ONLY_ON_CHANNEL.get(parameter)
            ) is not None and accept_channel != channel_no:
                return True
        if paramset_key == ParamsetKey.MASTER:
            if parameter in self._custom_un_ignore_parameters_by_device_paramset_key.get(
                device_type_l, {}
            ).get(channel_no, {}).get(ParamsetKey.MASTER, []):
                return False  # pragma: no cover

            dt_short = tuple(
                filter(
                    device_type_l.startswith,
                    self._un_ignore_parameters_by_device_paramset_key,
                )
            )
            if dt_short and parameter not in self._un_ignore_parameters_by_device_paramset_key.get(
                dt_short[0], {}
            ).get(channel_no, {}).get(ParamsetKey.MASTER, []):
                return True

        return False

    def _parameter_is_un_ignored(
        self,
        device_type: str,
        channel_no: int | None,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """
        Return if parameter is on an un_ignore list.

        This can be either be the users unignore file, or in the
        predefined _UN_IGNORE_PARAMETERS_BY_DEVICE.
        """
        device_type_l = device_type.lower()

        # check if parameter is in custom_un_ignore
        if parameter in self._un_ignore_parameters_general[paramset_key]:
            return True

        # check if parameter is in custom_un_ignore with paramset_key
        if parameter in self._custom_un_ignore_parameters_by_device_paramset_key.get(
            device_type_l, {}
        ).get(channel_no, {}).get(paramset_key, set()):
            return True  # pragma: no cover

        # check if parameter is in _UN_IGNORE_PARAMETERS_BY_DEVICE
        if (
            un_ignore_parameters := _get_value_from_dict_by_wildcard_key(
                search_elements=self._un_ignore_parameters_by_device_lower,
                compare_with=device_type_l,
            )
        ) and parameter in un_ignore_parameters:
            return True

        return False

    @lru_cache(maxsize=4096)
    def parameter_is_un_ignored(
        self,
        device_type: str,
        channel_no: int | None,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """
        Return if parameter is on an un_ignore list.

        Additionally to _parameter_is_un_ignored these parameters
        from _RELEVANT_MASTER_PARAMSETS_BY_DEVICE are unignored.
        """
        dt_short = tuple(
            filter(
                device_type.lower().startswith,
                self._un_ignore_parameters_by_device_paramset_key,
            )
        )

        # check if parameter is in _RELEVANT_MASTER_PARAMSETS_BY_DEVICE
        if dt_short and parameter in self._un_ignore_parameters_by_device_paramset_key.get(
            dt_short[0], {}
        ).get(channel_no, {}).get(paramset_key, set()):
            return True

        return self._parameter_is_un_ignored(
            device_type=device_type,
            channel_no=channel_no,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    def _add_line_to_cache(self, line: str) -> None:
        """
        Add line to from un ignore file to cache.

        Add data to relevant_master_paramsets_by_device and
        un_ignore_parameters_by_device from file.
        """
        if "@" in line:
            # add parameter@devicetype:channel_no:paramset_key
            data = line.split("@")
            if len(data) != 2:
                _LOGGER.warning(
                    "ADD_LINE_TO_CACHE failed: "
                    "Could not add line '%s' to un ignore cache. "
                    "Only one @ expected",
                    line,
                )
                return
            parameter = data[0]
            device_data = data[1].split(":")
            if len(device_data) != 3:
                _LOGGER.warning(
                    "ADD_LINE_TO_CACHE failed: "
                    "Could not add line '%s' to un ignore cache. "
                    "4 arguments expected: e.g. TEMPERATURE@HmIP-BWTH:1:VALUES",
                    line,
                )
                return
            device_type = device_data[0].lower()
            channel_no = int(device_data[1])
            paramset_key = device_data[2]
            if device_type not in self._custom_un_ignore_parameters_by_device_paramset_key:
                self._custom_un_ignore_parameters_by_device_paramset_key[device_type] = {}
            if (
                channel_no
                not in self._custom_un_ignore_parameters_by_device_paramset_key[device_type]
            ):
                self._custom_un_ignore_parameters_by_device_paramset_key[device_type][
                    channel_no
                ] = {}
            if (
                paramset_key
                not in self._custom_un_ignore_parameters_by_device_paramset_key[device_type][
                    channel_no
                ]
            ):
                self._custom_un_ignore_parameters_by_device_paramset_key[device_type][channel_no][
                    paramset_key
                ] = set()
            self._custom_un_ignore_parameters_by_device_paramset_key[device_type][channel_no][
                paramset_key
            ].add(parameter)

            if paramset_key == ParamsetKey.MASTER:
                if device_type not in self._relevant_master_paramsets_by_device:
                    self._relevant_master_paramsets_by_device[device_type] = set()
                self._relevant_master_paramsets_by_device[device_type].add(channel_no)

        elif ":" in line:
            # add parameter:paramset_key
            data = line.split(":")
            if len(data) != 2:
                _LOGGER.warning(
                    "ADD_LINE_TO_CACHE failed: "
                    "Could not add line '%s' to un ignore cache. "
                    "2 arguments expected: e.g. TEMPERATURE:VALUES",
                    line,
                )
                return
            paramset_key = data[0]
            parameter = data[1]
            if paramset_key in (ParamsetKey.VALUES, ParamsetKey.MASTER):
                self._un_ignore_parameters_general[paramset_key].add(parameter)
        else:
            # add parameter
            self._un_ignore_parameters_general[ParamsetKey.VALUES].add(line)

    @lru_cache(maxsize=1024)
    def parameter_is_hidden(
        self,
        device_type: str,
        channel_no: int | None,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """
        Return if parameter should be hidden.

        This is required to determine the entity usage.
        Return only hidden parameters, that are no defined in the unignore file.
        """
        return parameter in _HIDDEN_PARAMETERS and not self._parameter_is_un_ignored(
            device_type=device_type,
            channel_no=channel_no,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    def is_relevant_paramset(
        self,
        device_type: str,
        paramset_key: str,
        channel_no: int | None,
    ) -> bool:
        """
        Return if a paramset is relevant.

        Required to load MASTER paramsets, which are not initialized by default.
        """
        if paramset_key == ParamsetKey.VALUES:
            return True
        if channel_no is not None and paramset_key == ParamsetKey.MASTER:
            for (
                d_type,
                channel_nos,
            ) in self._relevant_master_paramsets_by_device.items():
                if channel_no in channel_nos and hms.element_matches_key(
                    search_elements=d_type,
                    compare_with=device_type,
                ):
                    return True
        return False

    async def load(self) -> None:
        """Load custom un ignore parameters from disk."""

        def _load() -> None:
            if not hms.check_or_create_directory(self._storage_folder):
                return  # pragma: no cover
            if not os.path.exists(
                os.path.join(self._storage_folder, _FILE_CUSTOM_UN_IGNORE_PARAMETERS)
            ):
                _LOGGER.debug(
                    "LOAD: No file found in %s",
                    self._storage_folder,
                )
                return

            try:
                with open(
                    file=os.path.join(
                        self._storage_folder,
                        _FILE_CUSTOM_UN_IGNORE_PARAMETERS,
                    ),
                    encoding=DEFAULT_ENCODING,
                ) as fptr:
                    for file_line in fptr.readlines():
                        if "#" not in file_line:
                            self._raw_un_ignore_list.add(file_line.strip())
            except Exception as ex:
                _LOGGER.warning(
                    "LOAD failed: Could not read unignore file %s",
                    reduce_args(args=ex.args),
                )

        if self._central.config.load_un_ignore:
            await self._central.async_add_executor_job(_load)

        for line in self._raw_un_ignore_list:
            if "#" not in line:
                self._add_line_to_cache(line)


def check_ignore_parameters_is_clean() -> bool:
    """Check if a required parameter is in ignored parameters."""
    un_ignore_parameters_by_device: list[str] = []
    for params in _UN_IGNORE_PARAMETERS_BY_DEVICE.values():
        un_ignore_parameters_by_device.extend(params)

    should_not_be_ignored: list[str] = []
    for parameter in get_required_parameters():
        if (
            parameter in _IGNORED_PARAMETERS
            or parameter.endswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_END))
            or parameter.startswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_START))
        ) and parameter not in un_ignore_parameters_by_device:
            should_not_be_ignored.append(parameter)
    return len(should_not_be_ignored) == 0


def _get_value_from_dict_by_wildcard_key(
    search_elements: Mapping[str, Any],
    compare_with: str | None,
    do_wildcard_search: bool = True,
) -> Any | None:
    """Return the dict value by wildcard type."""
    if compare_with is None:
        return None

    for key, value in search_elements.items():
        if do_wildcard_search:
            if key.lower().startswith(compare_with.lower()):
                return value
        elif key.lower() == compare_with.lower():
            return value
    return None
