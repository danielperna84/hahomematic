"""Helper functions used within hahomematic."""
from __future__ import annotations

import base64
from collections.abc import Collection
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from functools import cache
import logging
import os
import re
import socket
import ssl
from typing import Any

from hahomematic.const import (
    CCU_PASSWORD_PATTERN,
    FILE_DEVICES,
    FILE_PARAMSETS,
    INIT_DATETIME,
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
)
from hahomematic.exceptions import HaHomematicException

_LOGGER = logging.getLogger(__name__)


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
    username: str,
    password: str,
) -> list[tuple[str, str]]:
    """Build XML-RPC API header."""
    cred_bytes = f"{username}:{password}".encode()
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
                "CHECK_OR_CREATE_DIRECTORY failed: Unable to create directory %s ('%s')",
                directory,
                ose.strerror,
            )
            raise HaHomematicException from ose

    return True


def parse_sys_var(data_type: str | None, raw_value: Any) -> Any:
    """Parse system variables to fix type."""
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
        raise TypeError("invalid literal for boolean. Not a string.")

    lower_value = value.lower()
    return lower_value in ["y", "yes", "t", "true", "on", "1"]


def check_password(password: str | None) -> bool:
    """Check password."""
    if password is None:
        return False
    return re.fullmatch(CCU_PASSWORD_PATTERN, password) is not None


def get_tls_context(verify_tls: bool) -> ssl.SSLContext:
    """Return tls verified/unverified ssl/tls context."""
    if verify_tls:
        ssl_context = ssl.create_default_context()
    else:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def get_channel_address(device_address: str, channel_no: int | None) -> str:
    """Return the channel address."""
    return device_address if channel_no is None else f"{device_address}:{channel_no}"


def get_device_address(address: str) -> str:
    """Return the device part of an address."""
    return get_split_channel_address(channel_address=address)[0]


def get_channel_no(address: str) -> int | None:
    """Return the channel part of an address."""
    return get_split_channel_address(channel_address=address)[1]


@cache
def get_split_channel_address(channel_address: str) -> tuple[str, int | None]:
    """Return the device part of an address."""
    if ":" in channel_address:
        device_address, channel_no = channel_address.split(":")
        return device_address, int(channel_no)
    return channel_address, None


def updated_within_seconds(last_update: datetime, max_age_seconds: int | float) -> bool:
    """Entity has been updated within X minutes."""
    if last_update == INIT_DATETIME:
        return False
    delta = datetime.now() - last_update
    if delta.seconds < max_age_seconds:
        return True
    return False


def find_free_port() -> int:
    """Find a free port for XmlRpc server default port."""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def element_matches_key(
    search_elements: str | Collection[str],
    compare_with: str | None,
    do_wildcard_search: bool = True,
) -> bool:
    """Return if collection element is key."""
    if compare_with is None:
        return False

    if isinstance(search_elements, str):
        if do_wildcard_search:
            return compare_with.lower().startswith(search_elements.lower())
        return compare_with.lower() == search_elements.lower()
    if isinstance(search_elements, Collection):
        for element in search_elements:
            if do_wildcard_search:
                if compare_with.lower().startswith(element.lower()):
                    return True
            else:
                if compare_with.lower() == element.lower():
                    return True
    return False


@dataclass
class HubData:
    """Dataclass for hub entities."""

    name: str


@dataclass
class ProgramData(HubData):
    """Dataclass for programs."""

    pid: str
    is_active: bool
    is_internal: bool
    last_execute_time: str


@dataclass
class SystemVariableData(HubData):
    """Dataclass for system variables."""

    data_type: str | None = None
    unit: str | None = None
    value: bool | float | int | str | None = None
    value_list: list[str] | None = None
    max_value: float | int | None = None
    min_value: float | int | None = None
    extended_sysvar: bool = False


def cleanup_cache_dirs(instance_name: str, storage_folder: str) -> None:
    """Clean up the used cached directories."""
    cache_dir = f"{storage_folder}/cache"
    files_to_delete = [FILE_DEVICES, FILE_PARAMSETS]

    def _delete_file(file_name: str) -> None:
        if os.path.exists(os.path.join(cache_dir, file_name)):
            os.unlink(os.path.join(cache_dir, file_name))

    for file_to_delete in files_to_delete:
        _delete_file(file_name=f"{instance_name}_{file_to_delete}")


@dataclass
class Channel:
    """dataclass for a device channel."""

    type: str
