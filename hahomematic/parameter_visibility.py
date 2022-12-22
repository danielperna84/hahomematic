""" Module about parameter visibility within hahomematic """
from __future__ import annotations

import logging
import os
from typing import Final

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    DEFAULT_ENCODING,
    EVENT_CONFIG_PENDING,
    EVENT_ERROR,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    EVENT_UPDATE_PENDING,
    FILE_CUSTOM_UN_IGNORE_PARAMETERS,
    PARAM_CHANNEL_OPERATION_MODE,
    PARAM_TEMPERATURE_MAXIMUM,
    PARAM_TEMPERATURE_MINIMUM,
    PARAMSET_KEY_MASTER,
    PARAMSET_KEY_VALUES,
    HmPlatform,
)
import hahomematic.entity as hm_entity
from hahomematic.helpers import (
    check_or_create_directory,
    element_matches_key,
    get_value_from_dict_by_wildcard_key,
)

_LOGGER = logging.getLogger(__name__)

# {device_type: channel_no}
_RELEVANT_MASTER_PARAMSETS_BY_DEVICE: dict[
    str, tuple[tuple[int, ...], tuple[str, ...]]
] = {
    "HmIPW-DRBL4": ((1, 5, 9, 13), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-DRBLI4": (
        (1, 2, 3, 4, 5, 6, 7, 8, 9, 13, 17, 21),
        (PARAM_CHANNEL_OPERATION_MODE,),
    ),
    "HmIP-DRSI1": ((1,), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-DRSI4": ((1, 2, 3, 4), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-DRDI3": ((1, 2, 3), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-DSD-PCB": ((1,), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-FCI1": ((1,), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-FCI6": (tuple(range(1, 7)), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIPW-FIO6": (tuple(range(1, 7)), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-FSI16": ((1,), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-MIO16-PCB": ((13, 14, 15, 16), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIP-MOD-RC8": (tuple(range(1, 9)), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIPW-DRI16": (tuple(range(1, 17)), (PARAM_CHANNEL_OPERATION_MODE,)),
    "HmIPW-DRI32": (tuple(range(1, 33)), (PARAM_CHANNEL_OPERATION_MODE,)),
    "ALPHA-IP-RBG": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HM-CC-RT-DN": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HM-CC-VG-1": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIP-BWTH": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIP-eTRV": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIP-HEATING": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIP-STH": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIP-WTH": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIPW-STH": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
    "HmIPW-WTH": ((1,), (PARAM_TEMPERATURE_MAXIMUM, PARAM_TEMPERATURE_MINIMUM)),
}

ALLOW_INTERNAL_PARAMETERS = ("DIRECTION",)

_HIDDEN_PARAMETERS: tuple[str, ...] = (
    EVENT_CONFIG_PENDING,
    EVENT_ERROR,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    EVENT_UPDATE_PENDING,
    PARAM_CHANNEL_OPERATION_MODE,
    PARAM_TEMPERATURE_MAXIMUM,
    PARAM_TEMPERATURE_MINIMUM,
    "ACTIVITY_STATE",
    "DIRECTION",
)

# Parameters within the VALUES paramset for which we don't create entities.
_IGNORED_PARAMETERS: tuple[str, ...] = (
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
    "IDENTIFICATION_MODE_LCD_BACKLIGHT",
    "INCLUSION_UNSUPPORTED_DEVICE",
    "INHIBIT",
    "INSTALL_MODE",
    "LEVEL_COMBINED",
    "LEVEL_REAL",
    "OLD_LEVEL",
    "PARTY_SET_POINT_TEMPERATURE",
    "PARTY_TIME_END",
    "PARTY_TIME_START",
    "PROCESS",
    "QUICK_VETO_TIME",
    "RAMP_STOP",
    "RELOCK_DELAY",
    "SECTION",
    "SELF_CALIBRATION",
    "SET_SYMBOL_FOR_HEATING_PHASE",
    "SMOKE_DETECTOR_COMMAND",
    "STATE_UNCERTAIN",
    "SWITCH_POINT_OCCURED",
    "TEMPERATURE_LIMITER",
    "TEMPERATURE_OUT_OF_RANGE",
    "TIME_OF_OPERATION",
    "WOCHENPROGRAMM",
)

# Ignore Parameter that end with
_IGNORED_PARAMETERS_WILDCARDS_END: tuple[str, ...] = (
    "OVERFLOW",
    "OVERRUN",
    "REPORTING",
    "RESULT",
    "STATUS",
    "SUBMIT",
)

# Ignore Parameter that start with
_IGNORED_PARAMETERS_WILDCARDS_START: tuple[str, ...] = (
    "ADJUSTING",
    "ERR_TTM",
    "IDENTIFICATION_MODE_KEY_VISUAL",
    "IDENTIFY_",
    "PARTY_START",
    "PARTY_STOP",
    "STATUS_FLAG",
    "WEEK_PROGRAM",
    "WORKING",
)


# Parameters within the paramsets for which we create entities.
_UN_IGNORE_PARAMETERS_BY_DEVICE: dict[str, tuple[str, ...]] = {
    "HmIP-DLD": ("ERROR_JAMMED",),
    "HmIP-SWSD": ("SMOKE_DETECTOR_ALARM_STATUS",),
    "HM-Sec-Win": ("DIRECTION", "WORKING", "ERROR", "STATUS"),
    "HM-Sec-Key": ("DIRECTION", "ERROR"),
    "HmIP-PCBS-BAT": (
        "OPERATING_VOLTAGE",
        "LOW_BAT",
    ),  # To override ignore for HmIP-PCBS
}

# Parameters by device within the VALUES paramset for which we don't create entities.
_IGNORE_PARAMETERS_BY_DEVICE: dict[str, tuple[str, ...]] = {
    "CURRENT_ILLUMINATION": (
        "HmIP-SMI",
        "HmIP-SMO",
        "HmIP-SPI",
    ),
    "LOWBAT": (
        "HM-LC-Sw1-FM",
        "HM-LC-Sw1PBU-FM",
        "HM-LC-Sw1-Pl-DN-R1",
        "HM-LC-Sw1-PCB",
        "HM-LC-Sw4-DR",
        "HM-SwI-3-FM",
    ),
    "LOW_BAT": ("HmIP-BWTH", "HmIP-PCBS"),
    "OPERATING_VOLTAGE": (
        "ELV-SH-BS2",
        "HmIP-BS2",
        "HmIP-BDT",
        "HmIP-BSL",
        "HmIP-BSM",
        "HmIP-BWTH",
        "HmIP-DR",
        "HmIP-FDT",
        "HmIP-FSM",
        "HmIP-MOD-OC8",
        "HmIP-PCBS",
        "HmIP-PDT",
        "HmIP-PMFS",
        "HmIP-PS",
        "HmIP-SFD",
    ),
}

_ACCEPT_PARAMETER_ONLY_ON_CHANNEL: dict[str, int] = {"LOWBAT": 0}

_WRAP_ENTITY: dict[str | tuple[str, ...], dict[str, HmPlatform]] = {
    ("HmIP-eTRV", "HmIP-HEATING"): {"LEVEL": HmPlatform.SENSOR},
}


class ParameterVisibilityCache:
    """Cache for parameter visibility."""

    def __init__(
        self,
        central: hm_central.CentralUnit,
    ):
        self._central: Final[hm_central.CentralUnit] = central
        self._storage_folder: Final[str] = central.config.storage_folder

        # paramset_key, parameter
        self._un_ignore_parameters_general: dict[str, set[str]] = {
            PARAMSET_KEY_MASTER: set(),
            PARAMSET_KEY_VALUES: set(),
        }
        self._ignore_parameters_by_device_lower: dict[str, tuple[str, ...]] = {
            parameter: tuple(device_type.lower() for device_type in device_types)
            for parameter, device_types in _IGNORE_PARAMETERS_BY_DEVICE.items()
        }

        self._un_ignore_parameters_by_device_lower: dict[str, tuple[str, ...]] = {
            device_type.lower(): parameters
            for device_type, parameters in _UN_IGNORE_PARAMETERS_BY_DEVICE.items()
        }

        # device_type, channel_no, paramset_key, set[parameter]
        self._un_ignore_parameters_by_device_paramset_key: dict[
            str, dict[int, dict[str, set[str]]]
        ] = {}

        # unignore from custom unignore files
        # device_type, channel_no, paramset_key, parameter
        self._custom_un_ignore_parameters_by_device_paramset_key: dict[
            str, dict[int, dict[str, set[str]]]
        ] = {}

        # device_type, channel_no
        self._relevant_master_paramsets_by_device: dict[str, set[int]] = {}
        self._init()

    def _init(self) -> None:
        """
        Init relevant_master_paramsets_by_device and
        un_ignore_parameters_by_device from const.
        """
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
                    not in self._un_ignore_parameters_by_device_paramset_key[
                        device_type_l
                    ]
                ):
                    self._un_ignore_parameters_by_device_paramset_key[device_type_l][
                        channel_no
                    ] = {PARAMSET_KEY_MASTER: set()}
                for parameter in parameters:
                    self._un_ignore_parameters_by_device_paramset_key[device_type_l][
                        channel_no
                    ][PARAMSET_KEY_MASTER].add(parameter)

    def get_un_ignore_parameters(
        self, device_type: str, device_channel: int
    ) -> dict[str, tuple[str, ...]]:
        """Return un_ignore_parameters"""
        device_type_l = device_type.lower()
        un_ignore_parameters: dict[str, set[str]] = {}
        if device_type_l is not None and device_channel is not None:
            un_ignore_parameters = (
                self._custom_un_ignore_parameters_by_device_paramset_key.get(
                    device_type_l, {}
                ).get(device_channel, {})
            )
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

    def ignore_parameter(
        self,
        device_type: str,
        device_channel: int,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Check if parameter can be ignored."""
        device_type_l = device_type.lower()

        if paramset_key == PARAMSET_KEY_VALUES:
            if self.parameter_is_un_ignored(
                device_type=device_type,
                device_channel=device_channel,
                paramset_key=paramset_key,
                parameter=parameter,
            ):
                return False

            if (
                parameter in _IGNORED_PARAMETERS
                or parameter.endswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_END))
                or parameter.startswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_START))
                or element_matches_key(
                    search_elements=self._ignore_parameters_by_device_lower.get(
                        parameter, []
                    ),
                    compare_with=device_type_l,
                )
            ):
                return True

            if (
                accept_channel := _ACCEPT_PARAMETER_ONLY_ON_CHANNEL.get(parameter)
            ) is not None:
                if accept_channel != device_channel:
                    return True
        if paramset_key == PARAMSET_KEY_MASTER:
            if (
                parameter
                in self._custom_un_ignore_parameters_by_device_paramset_key.get(
                    device_type_l, {}
                )
                .get(device_channel, {})
                .get(PARAMSET_KEY_MASTER, [])
            ):
                return False

            dt_short = list(
                filter(
                    device_type_l.startswith,
                    self._un_ignore_parameters_by_device_paramset_key,
                )
            )
            if (
                dt_short
                and parameter
                not in self._un_ignore_parameters_by_device_paramset_key.get(
                    dt_short[0], {}
                )
                .get(device_channel, {})
                .get(PARAMSET_KEY_MASTER, [])
            ):
                return True

        return False

    def parameter_is_un_ignored(
        self,
        device_type: str,
        device_channel: int,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Return if parameter is on un_ignore list"""

        device_type_l = device_type.lower()

        if parameter in self._un_ignore_parameters_general[paramset_key]:
            return True

        # also check if parameter is in custom_un_ignore
        if parameter in self._custom_un_ignore_parameters_by_device_paramset_key.get(
            device_type_l, {}
        ).get(device_channel, {}).get(paramset_key, set()):
            return True

        dt_short = list(
            filter(
                device_type_l.startswith,
                self._un_ignore_parameters_by_device_paramset_key,
            )
        )

        if dt_short:
            if parameter in self._un_ignore_parameters_by_device_paramset_key.get(
                dt_short[0], {}
            ).get(device_channel, {}).get(paramset_key, set()):
                return True

        if un_ignore_parameters := get_value_from_dict_by_wildcard_key(
            search_elements=self._un_ignore_parameters_by_device_lower,
            compare_with=device_type_l,
        ):
            if parameter in un_ignore_parameters:
                return True

        return False

    def _add_line_to_cache(self, line: str) -> None:
        """
        Add line to from un ignore file to cache.
        Add data to relevant_master_paramsets_by_device and
        un_ignore_parameters_by_device from file.
        """
        try:
            line = line.strip()
            if "@" in line:
                # add parameter@devicetype:channel_no:paramset_key
                data = line.split("@")
                if len(data) != 2:
                    _LOGGER.warning(
                        "add_line_to_cache failed: "
                        "Could not add line '%s' to un ignore cache. "
                        "Only one @ expected.",
                        line,
                    )
                    return
                parameter = data[0]
                device_data = data[1].split(":")
                if len(device_data) != 3:
                    _LOGGER.warning(
                        "add_line_to_cache failed: "
                        "Could not add line '%s' to un ignore cache. "
                        "4 arguments expected: e.g. TEMPERATURE@HmIP-BWTH:1:VALUES.",
                        line,
                    )
                    return
                device_type = device_data[0].lower()
                channel_no = int(device_data[1])
                paramset_key = device_data[2]
                if (
                    device_type
                    not in self._custom_un_ignore_parameters_by_device_paramset_key
                ):
                    self._custom_un_ignore_parameters_by_device_paramset_key[
                        device_type
                    ] = {}
                if (
                    channel_no
                    not in self._custom_un_ignore_parameters_by_device_paramset_key[
                        device_type
                    ]
                ):
                    self._custom_un_ignore_parameters_by_device_paramset_key[
                        device_type
                    ][channel_no] = {}
                if (
                    paramset_key
                    not in self._custom_un_ignore_parameters_by_device_paramset_key[
                        device_type
                    ][channel_no]
                ):
                    self._custom_un_ignore_parameters_by_device_paramset_key[
                        device_type
                    ][channel_no][paramset_key] = set()
                self._custom_un_ignore_parameters_by_device_paramset_key[device_type][
                    channel_no
                ][paramset_key].add(parameter)

                if paramset_key == PARAMSET_KEY_MASTER:
                    if device_type not in self._relevant_master_paramsets_by_device:
                        self._relevant_master_paramsets_by_device[device_type] = set()
                    self._relevant_master_paramsets_by_device[device_type].add(
                        channel_no
                    )

            elif ":" in line:
                # add parameter:paramset_key
                data = line.split(":")
                if len(data) != 2:
                    _LOGGER.warning(
                        "add_line_to_cache failed: "
                        "Could not add line '%s' to un ignore cache. "
                        "2 arguments expected: e.g. TEMPERATURE:VALUES.",
                        line,
                    )
                    return
                paramset_key = data[0]
                parameter = data[1]
                if paramset_key in (PARAMSET_KEY_VALUES, PARAMSET_KEY_MASTER):
                    self._un_ignore_parameters_general[paramset_key].add(parameter)
            else:
                # add parameter
                self._un_ignore_parameters_general[PARAMSET_KEY_VALUES].add(line)
        except Exception:
            _LOGGER.warning(
                "add_line_to_cache failed: Could not add line '%s' to un ignore cache.",
                line,
            )

    def parameter_is_hidden(
        self,
        device_type: str,
        device_channel: int,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Return if parameter should be hidden"""
        return parameter in _HIDDEN_PARAMETERS and not self.parameter_is_un_ignored(
            device_type=device_type,
            device_channel=device_channel,
            paramset_key=paramset_key,
            parameter=parameter,
        )

    def is_relevant_paramset(
        self,
        device_type: str,
        paramset_key: str,
        device_channel: int,
    ) -> bool:
        """Return if a paramset is relevant."""
        if paramset_key == PARAMSET_KEY_VALUES:
            return True
        if device_channel is not None and paramset_key == PARAMSET_KEY_MASTER:
            for (
                d_type,
                channel_nos,
            ) in self._relevant_master_paramsets_by_device.items():
                if device_channel in channel_nos and element_matches_key(
                    search_elements=d_type,
                    compare_with=device_type,
                ):
                    return True
        return False

    def wrap_entity(self, wrapped_entity: hm_entity.GenericEntity) -> HmPlatform | None:
        """Check if parameter of a device should be wrapped to a different platform."""

        for devices, wrapper_def in _WRAP_ENTITY.items():
            if element_matches_key(
                search_elements=devices,
                compare_with=wrapped_entity.device.device_type,
            ):
                if wrapped_entity.parameter in wrapper_def:
                    return wrapper_def[wrapped_entity.parameter]
        return None

    async def load(self) -> None:
        """Load custom un ignore parameters from disk."""

        def _load() -> None:
            if not check_or_create_directory(self._storage_folder):
                return
            if not os.path.exists(
                os.path.join(self._storage_folder, FILE_CUSTOM_UN_IGNORE_PARAMETERS)
            ):
                _LOGGER.debug(
                    "load: No file found in %s",
                    self._storage_folder,
                )
                return

            try:
                with open(
                    file=os.path.join(
                        self._storage_folder,
                        FILE_CUSTOM_UN_IGNORE_PARAMETERS,
                    ),
                    mode="r",
                    encoding=DEFAULT_ENCODING,
                ) as fptr:
                    for line in fptr.readlines():
                        self._add_line_to_cache(line)
            except Exception as ex:
                _LOGGER.warning(
                    "load failed: Could not read unignore file %s",
                    ex.args,
                )

        await self._central.async_add_executor_job(_load)
