"""
Helper functions used within hahomematic
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
import logging
import os
import ssl
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    HM_VIRTUAL_REMOTE_ADDRESSES,
    HUB_ADDRESS,
    INIT_DATETIME,
    PARAMETER_FRIENDLY_NAME,
    SYSVAR_ADDRESS,
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
    TYPE_BOOL,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
    HmEntityUsage,
)
import hahomematic.device as hm_device
import hahomematic.devices.entity_definition as hm_entity_definition
from hahomematic.exceptions import HaHomematicException

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
    if (
        address in (HUB_ADDRESS, SYSVAR_ADDRESS)
        or address.startswith("INT000")
        or address.split(":")[0] in HM_VIRTUAL_REMOTE_ADDRESSES
    ):
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
            raise HaHomematicException from ose

    return True


def parse_ccu_sys_var(data_type: str | None, raw_value: Any) -> Any:
    """Helper to parse type of system variables of CCU."""
    # pylint: disable=no-else-return
    if not data_type:
        return raw_value
    if data_type in (SYSVAR_TYPE_ALARM, SYSVAR_TYPE_LOGIC):
        return raw_value == "true"
    if data_type == SYSVAR_HM_TYPE_FLOAT:
        return float(raw_value)
    if data_type in (SYSVAR_HM_TYPE_INTEGER, SYSVAR_TYPE_LIST):
        return int(raw_value)
    return raw_value


def parse_sys_var(data_type: str | None, raw_value: Any) -> Any:
    """Helper to parse type of system variables."""
    # pylint: disable=no-else-return
    if not data_type:
        return raw_value
    if data_type in (SYSVAR_TYPE_ALARM, SYSVAR_TYPE_LOGIC):
        return to_bool(raw_value)
    if data_type == SYSVAR_HM_TYPE_FLOAT:
        return float(raw_value)
    if data_type in (SYSVAR_HM_TYPE_INTEGER, SYSVAR_TYPE_LIST):
        return int(raw_value)
    return raw_value


def to_bool(value: Any) -> bool:
    """Convert defined string values to bool."""
    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        raise ValueError("invalid literal for boolean. Not a string.")

    valid = {
        "y": True,
        "yes": True,
        "t": True,
        "true": True,
        "on": True,
        "1": True,
        "n": False,
        "no": False,
        "f": False,
        "false": False,
        "off": False,
        "0": False,
    }

    lower_value = value.lower()
    if lower_value in valid:
        return valid[lower_value]

    raise ValueError(f"invalid literal for boolean: {value}.")


def get_entity_name(
    central: hm_central.CentralUnit,
    device: hm_device.HmDevice,
    channel_no: int,
    parameter: str,
) -> EntityNameData:
    """generate name for entity"""
    channel_address = f"{device.device_address}:{channel_no}"
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        new_parameter = parameter
        # Check if friendly name is available for parameter.
        if (friendly_name := PARAMETER_FRIENDLY_NAME.get(parameter)) is not None:
            new_parameter = friendly_name
        p_name = new_parameter.title().replace("_", " ")

        if _check_channel_name_with_channel_no(name=channel_name):
            c_name = channel_name.split(":")[0]
            c_postfix = ""
            if central.paramset_descriptions.has_multiple_channels(
                channel_address=channel_address, parameter=parameter
            ):
                c_postfix = "" if channel_no == 0 else f" ch{channel_no}"
            entity_name = EntityNameData(
                device_name=device.name,
                channel_name=c_name,
                parameter_name=f"{p_name}{c_postfix}",
            )
        else:
            entity_name = EntityNameData(
                device_name=device.name,
                channel_name=channel_name,
                parameter_name=p_name,
            )
        return entity_name

    _LOGGER.debug(
        "get_entity_name: Using unique_id for %s %s %s",
        device.device_type,
        channel_address,
        parameter,
    )
    return EntityNameData()


def get_event_name(
    central: hm_central.CentralUnit,
    device: hm_device.HmDevice,
    channel_no: int,
    parameter: str,
) -> EntityNameData:
    """generate name for event"""
    channel_address = f"{device.device_address}:{channel_no}"
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        p_name = parameter.title().replace("_", " ")
        if _check_channel_name_with_channel_no(name=channel_name):
            d_name = channel_name.split(":")[0]
            c_name = "" if channel_no == 0 else f" Channel {channel_no}"
            event_name = EntityNameData(
                device_name=device.name,
                channel_name=d_name,
                parameter_name=f"{c_name} {p_name}",
            )
        else:
            event_name = EntityNameData(
                device_name=device.name,
                channel_name=channel_name,
                parameter_name=p_name,
            )
        return event_name

    _LOGGER.debug(
        "Helper.get_event_name: Using unique_id for %s %s %s",
        device.device_type,
        channel_address,
        parameter,
    )
    return EntityNameData()


def get_custom_entity_name(
    central: hm_central.CentralUnit,
    device: hm_device.HmDevice,
    channel_no: int,
    is_only_primary_channel: bool,
    usage: HmEntityUsage,
) -> EntityNameData:
    """Rename name for custom entity"""
    if channel_name := _get_base_name_from_channel_or_device(
        central=central,
        device=device,
        channel_no=channel_no,
    ):
        if is_only_primary_channel and _check_channel_name_with_channel_no(
            name=channel_name
        ):
            return EntityNameData(
                device_name=device.name, channel_name=channel_name.split(":")[0]
            )
        if _check_channel_name_with_channel_no(name=channel_name):
            c_name = channel_name.split(":")[0]
            p_name = channel_name.split(":")[1]
            marker = "ch" if usage == HmEntityUsage.CE_PRIMARY else "vch"
            p_name = f"{marker}{p_name}"
            return EntityNameData(
                device_name=device.name, channel_name=c_name, parameter_name=p_name
            )
        return EntityNameData(device_name=device.name, channel_name=channel_name)

    _LOGGER.debug(
        "Helper.get_custom_entity_name: Using unique_id for %s %s %s",
        device.device_type,
        device.device_address,
        channel_no,
    )
    return EntityNameData()


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
    device: hm_device.HmDevice,
    channel_no: int,
) -> str | None:
    """Get the name from channel if it's not default, otherwise from device."""
    channel_address = f"{device.device_address}:{channel_no}"
    default_channel_name = f"{device.device_type} {channel_address}"
    name = central.device_details.get_name(channel_address)
    if name is None or name == default_channel_name:
        name = f"{device.name}:{channel_no}"
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
            return to_bool(value)
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
    value: bool | float | int | str | None = None
    value_list: list[str] | None = None
    max_value: float | int | None = None
    min_value: float | int | None = None
    extended_sysvar: bool = False


@dataclass
class EntityNameData:
    """Dataclass for entity name parts"""

    device_name: str | None = None
    channel_name: str | None = None
    parameter_name: str | None = None

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        if self.channel_name and self.parameter_name:
            return f"{self.channel_name} {self.parameter_name}".strip()
        if self.channel_name:
            return self.channel_name.strip()
        return None

    @property
    def entity_name(self) -> str | None:
        """Return the name of the entity only name."""
        if self.device_name and self.name and self.name.startswith(self.device_name):
            return self.name.replace(self.device_name, "").strip()
        return self.name

    @property
    def full_name(self) -> str | None:
        """Return the full name of the entity."""
        if self.entity_name:
            return f"{self.device_name} {self.entity_name}".strip()
        return self.device_name
