""" Module about parameter visibility within hahomematic """
from __future__ import annotations

import logging
import os

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
    PARAMSET_KEY_MASTER,
    PARAMSET_KEY_VALUES,
)
import hahomematic.device as hm_device
from hahomematic.helpers import check_or_create_directory

_LOGGER = logging.getLogger(__name__)

# {device_type: channel_no}
_RELEVANT_MASTER_PARAMSETS_BY_DEVICE: dict[str, tuple[set[int], str]] = {
    "HmIPW-DRBL4": ({1, 5, 9, 13}, PARAM_CHANNEL_OPERATION_MODE),
    "HmIP-DRBLI4": ({9, 13, 17, 21}, PARAM_CHANNEL_OPERATION_MODE),
}

# Parameters within the paramsets for which we create entities.
_UN_IGNORE_PARAMETERS_BY_DEVICE: dict[str, list[str]] = {
    "DLD": ["ERROR_JAMMED"],  # HmIP-DLD
    "SD": ["SMOKE_DETECTOR_ALARM_STATUS"],  # HmIP-SWSD
    "HM-Sec-Win": ["DIRECTION", "WORKING", "ERROR", "STATUS"],  # HM-Sec-Win*
    "HM-Sec-Key": ["DIRECTION", "ERROR"],  # HM-Sec-Key*
}

HIDDEN_PARAMETERS: set[str] = {
    EVENT_CONFIG_PENDING,
    EVENT_ERROR,
    EVENT_STICKY_UN_REACH,
    EVENT_UN_REACH,
    EVENT_UPDATE_PENDING,
    PARAM_CHANNEL_OPERATION_MODE,
    "ACTIVITY_STATE",
    "DIRECTION",
}

# Parameters within the VALUES paramset for which we don't create entities.
_IGNORED_PARAMETERS: set[str] = {
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
    "WOCHENPROGRAMM",
}

# Ignore Parameter that end with
_IGNORED_PARAMETERS_WILDCARDS_END: set[str] = {
    "OVERFLOW",
    "OVERHEAT",
    "OVERRUN",
    "REPORTING",
    "RESULT",
    "STATUS",
    "SUBMIT",
    "WORKING",
}

# Ignore Parameter that start with
_IGNORED_PARAMETERS_WILDCARDS_START: set[str] = {
    "ADJUSTING",
    "ERR_TTM",
    "ERROR",
    "IDENTIFICATION_MODE_KEY_VISUAL",
    "IDENTIFY_",
    "PARTY_START",
    "PARTY_STOP",
    "STATUS_FLAG",
    "WEEK_PROGRAM",
}
_ACCEPT_PARAMETER_ONLY_ON_CHANNEL: dict[str, int] = {"LOWBAT": 0}


class ParameterVisibilityCache:
    """Cache for parameter visibility."""

    def __init__(
        self,
        central: hm_central.CentralUnit,
    ):
        self._central = central
        self._storage_folder = self._central.central_config.storage_folder

        # paramset_key, parameter
        self._un_ignore_parameters_general: dict[str, set[str]] = {
            PARAMSET_KEY_MASTER: set(),
            PARAMSET_KEY_VALUES: set(),
        }
        # device_type, channel_no, paramset_key, list[parameter]
        self._un_ignore_parameters_by_device: dict[
            str, dict[int, dict[str, set[str]]]
        ] = {}
        # device_type, channel_no
        self._relevant_master_paramsets_by_device: dict[str, set[int]] = {}
        self._init()

    def _init(self) -> None:
        """Init relevant_master_paramsets_by_device and un_ignore_parameters_by_device from const"""
        for (
            device_type,
            channels_parameter,
        ) in _RELEVANT_MASTER_PARAMSETS_BY_DEVICE.items():
            channel_nos, parameter = channels_parameter
            if device_type not in self._relevant_master_paramsets_by_device:
                self._relevant_master_paramsets_by_device[device_type] = set()
            if device_type not in self._un_ignore_parameters_by_device:
                self._un_ignore_parameters_by_device[device_type] = {}
            for channel_no in channel_nos:
                self._relevant_master_paramsets_by_device[device_type].add(channel_no)
                if channel_no not in self._un_ignore_parameters_by_device[device_type]:
                    self._un_ignore_parameters_by_device[device_type][channel_no] = {
                        PARAMSET_KEY_MASTER: set()
                    }

                self._un_ignore_parameters_by_device[device_type][channel_no][
                    PARAMSET_KEY_MASTER
                ].add(parameter)

    def get_un_ignore_parameters(
        self, device_type: str, device_channel: int
    ) -> dict[str, set[str]]:
        """Return un_ignore_parameters"""
        un_ignore_parameters: dict[str, set[str]] = {}
        if device_type is not None and device_channel is not None:
            un_ignore_parameters = self._un_ignore_parameters_by_device.get(
                device_type, {}
            ).get(device_channel, {})

        for (
            paramset_key,
            un_ignore_params,
        ) in self._un_ignore_parameters_general.items():
            if paramset_key not in un_ignore_parameters:
                un_ignore_parameters[paramset_key] = set()
            un_ignore_parameters[paramset_key].update(un_ignore_params)

        return un_ignore_parameters

    def ignore_parameter(
        self,
        device: hm_device.HmDevice,
        device_channel: int,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Check if parameter can be ignored."""
        if paramset_key == PARAMSET_KEY_VALUES:
            if self.parameter_is_un_ignored(
                device=device,
                device_channel=device_channel,
                paramset_key=paramset_key,
                parameter=parameter,
            ):
                return False
            if (
                parameter in _IGNORED_PARAMETERS
                or parameter.endswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_END))
                or parameter.startswith(tuple(_IGNORED_PARAMETERS_WILDCARDS_START))
            ):
                return True
            if (
                accept_channel := _ACCEPT_PARAMETER_ONLY_ON_CHANNEL.get(parameter)
            ) is not None:
                if accept_channel != device_channel:
                    return True
        if paramset_key == PARAMSET_KEY_MASTER:
            if parameter not in self._un_ignore_parameters_by_device.get(
                device.device_type, {}
            ).get(device_channel, {}).get(PARAMSET_KEY_MASTER, []):
                return True
        return False

    def parameter_is_un_ignored(
        self,
        device: hm_device.HmDevice,
        device_channel: int,
        paramset_key: str,
        parameter: str,
    ) -> bool:
        """Return if parameter is on un_ignore list"""
        if parameter in self._un_ignore_parameters_general[paramset_key]:
            return True

        if parameter in self._un_ignore_parameters_by_device.get(
            device.device_type, {}
        ).get(device_channel, {}).get(paramset_key, set()):
            return True

        if parameter in self._un_ignore_parameters_by_device.get(
            device.sub_type, {}
        ).get(device_channel, {}).get(paramset_key, set()):
            return True

        if device.sub_type and device.sub_type in _UN_IGNORE_PARAMETERS_BY_DEVICE:
            un_ignore_parameters = _UN_IGNORE_PARAMETERS_BY_DEVICE[device.sub_type]
            if parameter in un_ignore_parameters:
                return True

        if device.device_type.startswith(tuple(_UN_IGNORE_PARAMETERS_BY_DEVICE)):
            for (
                device_type,
                un_ignore_parameters,
            ) in _UN_IGNORE_PARAMETERS_BY_DEVICE.items():
                if device.device_type.startswith(device_type):
                    if parameter in un_ignore_parameters:
                        return True
        return False

    def _add_line_to_cache(self, line: str) -> None:
        """
        Add line to from un ignore file to cache.
        Add data to relevant_master_paramsets_by_device and un_ignore_parameters_by_device from file.
        """
        try:
            line = line.strip()
            if "@" in line:
                # add parameter@devicetype:channel_no:paramset_key
                data = line.split("@")
                if len(data) != 2:
                    _LOGGER.warning(
                        "add_line_to_cache: Could not add line '%s' to un ignore cache. Only one @ expected.",
                        line,
                    )
                    return
                parameter = data[0]
                device_data = data[1].split(":")
                if len(device_data) != 3:
                    _LOGGER.warning(
                        "add_line_to_cache: Could not add line '%s' to un ignore cache. 4 arguments expected: e.g. TEMPERATURE@HmIP-BWTH:1:VALUES.",
                        line,
                    )
                    return
                device_type = device_data[0]
                channel_no = int(device_data[1])
                paramset_key = device_data[2]
                if device_type not in self._un_ignore_parameters_by_device:
                    self._un_ignore_parameters_by_device[device_type] = {}
                if channel_no not in self._un_ignore_parameters_by_device[device_type]:
                    self._un_ignore_parameters_by_device[device_type][channel_no] = {}
                if (
                    paramset_key
                    not in self._un_ignore_parameters_by_device[device_type][channel_no]
                ):
                    self._un_ignore_parameters_by_device[device_type][channel_no][
                        paramset_key
                    ] = set()
                self._un_ignore_parameters_by_device[device_type][channel_no][
                    paramset_key
                ].add(parameter)

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
                        "add_line_to_cache: Could not add line '%s' to un ignore cache. 2 arguments expected: e.g. TEMPERATURE:VALUES.",
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
                "add_line_to_cache: Could not add line '%s' to un ignore cache.", line
            )

    def is_relevant_paramset(
        self,
        device_type: str,
        sub_type: str | None,
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
                if device_channel in channel_nos and (
                    device_type.lower() == d_type.lower()
                    or (sub_type and sub_type.lower() == d_type.lower())
                    or device_type.lower().startswith(d_type.lower())
                ):
                    return True
        return False

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
                    "load: Could not read unignore file %s",
                    ex.args,
                )

        await self._central.async_add_executor_job(_load)