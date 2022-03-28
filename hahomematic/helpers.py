"""
Helper functions used within hahomematic
"""
from __future__ import annotations

import base64
from datetime import datetime
from distutils import util
import logging
import os
import ssl
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    ATTR_HM_ALARM,
    ATTR_HM_LIST,
    ATTR_HM_LOGIC,
    ATTR_HM_NUMBER,
    ATTR_TYPE,
    ATTR_VALUE,
    INIT_DATETIME,
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


def generate_unique_id(
    domain: str,
    instance_name: str,
    address: str,
    parameter: str | None = None,
    prefix: str | None = None,
) -> str:
    """
    Build unique id from address and parameter.
    Instance_name is addionally used for heating groups.
    Prefix is used for events and buttons.
    """
    unique_id = address.replace(":", "_").replace("-", "_")
    if parameter:
        unique_id = f"{unique_id}_{parameter}"

    if prefix:
        unique_id = f"{prefix}_{unique_id}"
    if address.startswith("INT000"):
        return f"{domain}_{instance_name}_{unique_id}".lower()
    return f"{domain}_{unique_id}".lower()


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


def parse_ccu_sys_var(data: dict[str, Any]) -> Any:
    """Helper to parse type of system variables of CCU."""
    # pylint: disable=no-else-return
    if data[ATTR_TYPE] == ATTR_HM_LOGIC:
        return data[ATTR_VALUE] == "true"
    if data[ATTR_TYPE] == ATTR_HM_ALARM:
        return data[ATTR_VALUE] == "true"
    elif data[ATTR_TYPE] == ATTR_HM_NUMBER:
        return float(data[ATTR_VALUE])
    elif data[ATTR_TYPE] == ATTR_HM_LIST:
        return int(data[ATTR_VALUE])
    return data[ATTR_VALUE]


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
        if _check_channel_name_with_channel_no(name=entity_name):
            d_name = entity_name.split(":")[0]
            p_name = parameter.title().replace("_", " ")
            c_name = ""
            if central.paramset_descriptions.has_multiple_channels(
                channel_address=channel_address, parameter=parameter
            ):
                c_no = entity_name.split(":")[1]
                c_name = "" if c_no == "0" else f" ch{c_no}"
            entity_name = f"{d_name} {p_name}{c_name}"
        else:
            d_name = entity_name
            p_name = parameter.title().replace("_", " ")
            entity_name = f"{d_name} {p_name}"
        return entity_name

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
        if _check_channel_name_with_channel_no(name=event_name):
            d_name = event_name.split(":")[0]
            p_name = parameter.title().replace("_", " ")
            c_no = event_name.split(":")[1]
            c_name = "" if c_no == "0" else f" Channel {c_no}"
            event_name = f"{d_name}{c_name} {p_name}"
        else:
            d_name = event_name
            p_name = parameter.title().replace("_", " ")
            event_name = f"{d_name} {p_name}"
        return event_name

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
        return custom_entity_name

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
