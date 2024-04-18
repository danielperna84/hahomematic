"""Converters used by hahomematic."""

from __future__ import annotations

import ast
import logging
from typing import Any, Final, cast

from hahomematic.const import Parameter
from hahomematic.support import reduce_args

_LOGGER = logging.getLogger(__name__)


def _convert_cpv_to_hm_level(cpv: Any) -> Any:
    """Convert combined parameter value for hm level."""
    if isinstance(cpv, str) and cpv.startswith("0x"):
        return ast.literal_eval(cpv) / 100 / 2
    return cpv


def _convert_cpv_to_hmip_level(cpv: Any) -> Any:
    """Convert combined parameter value for hmip level."""
    return int(cpv) / 100


def convert_hm_level_to_cpv(hm_level: Any) -> Any:
    """Convert hm level to combined parameter value."""
    return format(int(hm_level * 100 * 2), "#04x")


CONVERTABLE_PARAMETERS: Final = (Parameter.COMBINED_PARAMETER, Parameter.LEVEL_COMBINED)

_COMBINED_PARAMETER_TO_HM_CONVERTER: Final = {
    Parameter.LEVEL_COMBINED: _convert_cpv_to_hm_level,
    Parameter.LEVEL: _convert_cpv_to_hmip_level,
    Parameter.LEVEL_2: _convert_cpv_to_hmip_level,
}

_COMBINED_PARAMETER_NAMES: Final = {"L": Parameter.LEVEL, "L2": Parameter.LEVEL_2}


def _convert_combined_parameter_to_paramset(cpv: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    paramset: dict[str, Any] = {}
    for cp_param_value in cpv.split(","):
        cp_param, value = cp_param_value.split("=")
        if parameter := _COMBINED_PARAMETER_NAMES.get(cp_param):
            if converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(parameter):
                paramset[parameter] = converter(value)
            else:
                paramset[parameter] = value
    return paramset


def _convert_level_combined_to_paramset(lcv: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    if "," in lcv:
        l1_value, l2_value = lcv.split(",")
        if converter := _COMBINED_PARAMETER_TO_HM_CONVERTER.get(Parameter.LEVEL_COMBINED):
            return {
                Parameter.LEVEL: converter(l1_value),
                Parameter.LEVEL_SLATS: converter(l2_value),
            }
    return {}


_COMBINED_PARAMETER_TO_PARAMSET_CONVERTER: Final = {
    Parameter.COMBINED_PARAMETER: _convert_combined_parameter_to_paramset,
    Parameter.LEVEL_COMBINED: _convert_level_combined_to_paramset,
}


def convert_combined_parameter_to_paramset(parameter: str, cpv: str) -> dict[str, Any]:
    """Convert combined parameter to paramset."""
    try:
        if converter := _COMBINED_PARAMETER_TO_PARAMSET_CONVERTER.get(parameter):  # type: ignore[call-overload]
            return cast(dict[str, Any], converter(cpv))
        _LOGGER.debug(
            "CONVERT_COMBINED_PARAMETER_TO_PARAMSET: No converter found for %s: %s", parameter, cpv
        )
    except Exception as ex:
        _LOGGER.debug(
            "CONVERT_COMBINED_PARAMETER_TO_PARAMSET: Convert failed %s", reduce_args(args=ex.args)
        )
    return {}
