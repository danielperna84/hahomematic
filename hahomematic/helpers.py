"""
Helper functions used within hahomematic
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from distutils import util
import logging
import os
import ssl
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    HUB_ADDRESS,
    INIT_DATETIME,
    PARAMETER_FRIENDLY_NAME,
    SYSVAR_ADDRESS,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
    SYSVAR_TYPE_NUMBER,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    HmEntityUsage,
)
import hahomematic.devices.entity_definition as hm_entity_definition
from hahomematic.exceptions import BaseHomematicException

_LOGGER = logging.getLogger(__name__)


class ClientException(Exception):
    """hahomematic Client exception."""


@dataclass
class HmDeviceInfo:
    """HM entity device information for HA device registry."""

    identifier: str
    interface: str | None = None
    address: str | None = None
    channel_no: int | None = None
    central_url: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    name: str | None = None
    room: str | None = None
    version: str | None = None
    central: str | None = None


def generate_unique_id(
    central: hm_central.CentralUnit,
    address: str,
    parameter: str | None = None,
    prefix: str | None = None,
) -> str:
    """
    Build unique id from address and parameter.
    Central id is addionally used for heating groups.
    Prefix is used for events and buttons.
    """
    unique_id = address.replace(":", "_").replace("-", "_")
    if parameter:
        unique_id = f"{unique_id}_{parameter}"

    if prefix:
        unique_id = f"{prefix}_{unique_id}"
    if address in (HUB_ADDRESS, SYSVAR_ADDRESS) or address.startswith("INT000"):
        return f"{central.domain}_{central.central_id}_{unique_id}".lower()
    return f"{central.domain}_{unique_id}".lower()


def build_xml_rpc_uri(
    host: str,
    port: int,
    path: str | None,
    tls: bool = False,
) -> str:
    """Build XML-RPC API URL from components."""
    scheme = "http"
    if not path:
        path = ""
    if path and not path.startswith("/"):
        path = f"/{path}"
    if tls:
        scheme += "s"
    return f"{scheme}://{host}:{port}{path}"


def build_headers(
    username: str | None = None,
    password: str | None = None,
) -> list[tuple[str, str]]:
    """Build XML-RPC API header."""
    cred_bytes = f"{username}:{password}".encode("utf-8")
    base64_message = base64.b64encode(cred_bytes).decode("utf-8")
    return [("Authorization", f"Basic {base64_message}")]


def check_or_create_directory(directory: str) -> bool:
    """Check / create directory."""
    if not directory:
        return False
    if not os.path.exists(directory):
        try:
            os.makedirs(directory)
        except OSError as ose:
            _LOGGER.error(
                "check_or_create_directory: Unable to create directory %s ('%s')",
                directory,
                ose.strerror,
            )
            raise BaseHomematicException from ose

    return True


def parse_ccu_sys_var(data_type: str | None, raw_value: Any) -> Any:
    """Helper to parse type of system variables of CCU."""
    # pylint: disable=no-else-return
    if not data_type:
        return raw_value
    if data_type == SYSVAR_TYPE_LOGIC:
        return raw_value == "true"
    if data_type == SYSVAR_TYPE_ALARM:
        return raw_value == "true"
    elif data_type == SYSVAR_TYPE_NUMBER:
        return float(raw_value)
    elif data_type == SYSVAR_TYPE_LIST:
        return int(raw_value)
    return raw_value


def parse_sys_var(data_type: str | None, raw_value: Any) -> Any:
    """Helper to parse type of system variables."""
    # pylint: disable=no-else-return
    if not data_type:
        return raw_value
    if data_type == SYSVAR_TYPE_LOGIC:
        return bool(raw_value)
    if data_type == SYSVAR_TYPE_ALARM:
        return bool(raw_value)
    elif data_type == SYSVAR_TYPE_NUMBER:
        return float(raw_value)
    elif data_type == SYSVAR_TYPE_LIST:
        return int(raw_value)
    return raw_value


def get_entity_name(
    central: hm_central.CentralUnit,
    channel_address: str,
    parameter: str,
    unique_id: str,
    device_type: str,
) -> str:
    """generate name for entity"""
    if entity_name := _get_base_name_from_channel_or_device(
        central=central,
        channel_address=channel_address,
        device_type=device_type,
    ):
        new_parameter = parameter
        # Check if friendly name is available for parameter.
        if (friendly_name := PARAMETER_FRIENDLY_NAME.get(parameter)) is not None:
            new_parameter = friendly_name
        p_name = new_parameter.title().replace("_", " ")

        if _check_channel_name_with_channel_no(name=entity_name):
            d_name = entity_name.split(":")[0]
            c_name = ""
            if central.paramset_descriptions.has_multiple_channels(
                channel_address=channel_address, parameter=parameter
            ):
                c_no = entity_name.split(":")[1]
                c_name = "" if c_no == "0" else f" ch{c_no}"
            entity_name = f"{d_name} {p_name}{c_name}"
        else:
            d_name = entity_name
            entity_name = f"{d_name} {p_name}"
        return entity_name.strip()

    _LOGGER.debug(
        "get_entity_name: Using unique_id for %s %s %s",
        device_type,
        channel_address,
        parameter,
    )
    return unique_id


def get_event_name(
    central: hm_central.CentralUnit,
    channel_address: str,
    parameter: str,
    unique_id: str,
    device_type: str,
) -> str:
    """generate name for event"""
    if event_name := _get_base_name_from_channel_or_device(
        central=central,
        channel_address=channel_address,
        device_type=device_type,
    ):
        p_name = parameter.title().replace("_", " ")
        if _check_channel_name_with_channel_no(name=event_name):
            d_name = event_name.split(":")[0]
            c_no = event_name.split(":")[1]
            c_name = "" if c_no == "0" else f" Channel {c_no}"
            event_name = f"{d_name}{c_name} {p_name}"
        else:
            d_name = event_name
            event_name = f"{d_name} {p_name}"
        return event_name.strip()

    _LOGGER.debug(
        "Helper.get_event_name: Using unique_id for %s %s %s",
        device_type,
        channel_address,
        parameter,
    )
    return unique_id


def get_custom_entity_name(
    central: hm_central.CentralUnit,
    device_address: str,
    unique_id: str,
    channel_no: int,
    device_type: str,
    is_only_primary_channel: bool,
    usage: HmEntityUsage,
) -> str:
    """Rename name for custom entity"""
    if custom_entity_name := _get_base_name_from_channel_or_device(
        central=central,
        channel_address=f"{device_address}:{channel_no}",
        device_type=device_type,
    ):
        if is_only_primary_channel and _check_channel_name_with_channel_no(
            name=custom_entity_name
        ):
            return custom_entity_name.split(":")[0]
        if _check_channel_name_with_channel_no(name=custom_entity_name):
            marker = " ch" if usage == HmEntityUsage.CE_PRIMARY else " vch"
            return custom_entity_name.replace(":", marker)
        return custom_entity_name.strip()

    _LOGGER.debug(
        "Helper.get_custom_entity_name: Using unique_id for %s %s %s",
        device_type,
        device_address,
        channel_no,
    )
    return unique_id


def _check_channel_name_with_channel_no(name: str) -> bool:
    """check if name contains channel and this is an int."""
    if name.count(":") == 1:
        channel_part = name.split(":")[1]
        try:
            int(channel_part)
            return True
        except ValueError:
            return False
    return False


def get_device_name(
    central: hm_central.CentralUnit, device_address: str, device_type: str
) -> str:
    """Return the cached name for a device, or an auto-generated."""
    if name := central.device_details.get_name(address=device_address):
        return name

    _LOGGER.debug(
        "Helper.get_device_name: Using auto-generated name for %s %s",
        device_type,
        device_address,
    )
    return get_generated_device_name(
        device_address=device_address, device_type=device_type
    )


def get_generated_device_name(device_address: str, device_type: str) -> str:
    """Return auto-generated device name."""
    return f"{device_type}_{device_address}"


def check_channel_is_only_primary_channel(
    current_channel: int, device_def: dict[str, Any], device_has_multiple_channels: bool
) -> bool:
    """Check if this channel is the only primary channel."""
    primary_channel: int = device_def[hm_entity_definition.ED_PRIMARY_CHANNEL]
    if primary_channel == current_channel and device_has_multiple_channels is False:
        return True
    return False


def _get_base_name_from_channel_or_device(
    central: hm_central.CentralUnit,
    channel_address: str,
    device_type: str,
) -> str | None:
    """Get the name from channel if it's not default, otherwise from device."""
    default_channel_name = f"{device_type} {channel_address}"
    name = central.device_details.get_name(channel_address)
    if name is None or name == default_channel_name:
        channel_no = get_device_channel(channel_address)
        if device_name := central.device_details.get_name(
            get_device_address(channel_address)
        ):
            name = f"{device_name}:{channel_no}"
    return name


def get_tls_context(verify_tls: bool) -> ssl.SSLContext:
    """Return tls verified/unverified ssl/tls context"""
    if verify_tls:
        ssl_context = ssl.create_default_context()
    else:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def get_device_address(address: str) -> str:
    """Return the device part of an address"""
    if ":" in address:
        return address.split(":")[0]
    return address


def get_device_channel(address: str) -> int:
    """Return the channel part of an address"""
    if ":" not in address:
        raise Exception("Address has no channel part.")
    return int(address.split(":")[1])


def get_channel_no(address: str) -> int | None:
    """Return the channel part of an address"""
    if ":" not in address:
        return None
    return int(address.split(":")[1])


def updated_within_seconds(last_update: datetime, age_seconds: int = 120) -> bool:
    """Entity has been updated within X minutes."""
    if last_update == INIT_DATETIME:
        return False
    delta = datetime.now() - last_update
    if delta.seconds < age_seconds:
        return True
    return False


def convert_value(value: Any, target_type: str) -> Any:
    """Convert to value to target_type"""
    if value is None:
        return None
    if target_type == TYPE_BOOL:
        if isinstance(value, str):
            return bool(util.strtobool(value))
        return bool(value)
    if target_type == TYPE_FLOAT:
        return float(value)
    if target_type == TYPE_INTEGER:
        return int(float(value))
    if target_type == TYPE_STRING:
        return str(value)
    return value


@dataclass
class SystemVariableData:
    """Dataclass for system variables."""

    name: str
    data_type: str | None = None
    unit: str | None = None
    value: Any | None = None
    value_list: list[str] | None = None
    max_value: Any | None = None
    min_value: Any | None = None
    internal: bool = False
