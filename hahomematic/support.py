"""Helper functions used within hahomematic."""
from __future__ import annotations

import base64
from collections.abc import Callable, Collection
import contextlib
from dataclasses import dataclass, field
from datetime import datetime
from functools import cache
import logging
import os
import re
import socket
import ssl
from typing import Any, TypeVar

import voluptuous as vol

from hahomematic.const import (
    CCU_PASSWORD_PATTERN,
    EVENT_DATA,
    EVENT_INTERFACE_ID,
    EVENT_TYPE,
    FILE_DEVICES,
    FILE_PARAMSETS,
    INIT_DATETIME,
    HmInterfaceEventType,
    HmSysvarType,
)
from hahomematic.exceptions import HaHomematicException

_LOGGER = logging.getLogger("hahomematic.support")

_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])

HM_INTERFACE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_INTERFACE_ID): str,
        vol.Required(EVENT_TYPE): HmInterfaceEventType,
        vol.Required(EVENT_DATA): vol.Schema(
            {vol.Required(vol.Any(str)): vol.Schema(vol.Any(str, int, bool))}
        ),
    }
)


def reduce_args(args: tuple[Any, ...]) -> tuple[Any, ...] | Any:
    """Return the first arg, if there is only one arg."""
    return args[0] if len(args) == 1 else args


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
            message = f"CHECK_OR_CREATE_DIRECTORY failed: Unable to create directory {directory} ('{ose.strerror}')"
            _LOGGER.error(message)
            raise HaHomematicException(message) from ose

    return True


def parse_sys_var(data_type: HmSysvarType | None, raw_value: Any) -> Any:
    """Parse system variables to fix type."""
    # pylint: disable=no-else-return
    if not data_type:
        return raw_value
    if data_type in (HmSysvarType.ALARM, HmSysvarType.LOGIC):
        return to_bool(raw_value)
    if data_type == HmSysvarType.HM_FLOAT:
        return float(raw_value)
    if data_type in (HmSysvarType.HM_INTEGER, HmSysvarType.LIST):
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
    if re.fullmatch(CCU_PASSWORD_PATTERN, password) is None:
        _LOGGER.warning(
            "CHECK_CONFIG: password contains not allowed characters. "
            "Use only allowed characters. See password regex: %s",
            CCU_PASSWORD_PATTERN,
        )
        return False
    return True


def get_tls_context(verify_tls: bool) -> ssl.SSLContext:
    """Return tls verified/unverified ssl/tls context."""
    sslcontext = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    if not verify_tls:
        sslcontext.check_hostname = False
        sslcontext.verify_mode = ssl.CERT_NONE
    with contextlib.suppress(AttributeError):
        # This only works for OpenSSL >= 1.0.0
        sslcontext.options |= ssl.OP_NO_COMPRESSION
    sslcontext.set_default_verify_paths()
    return sslcontext


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
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def element_matches_key(
    search_elements: str | Collection[str],
    compare_with: str | None,
    search_key: str | None = None,
    do_wildcard_search: bool = True,
) -> bool:
    """
    Return if collection element is key.

    A set search_key assumes that search_elements is initially a dict,
    and it tries to identify a matching key (wildcard) in the dict keys to use it on the dict.
    """
    if compare_with is None or not search_elements:
        return False

    if isinstance(search_elements, str):
        if do_wildcard_search:
            return compare_with.lower().startswith(
                search_elements.lower()
            )  # or search_elements.lower().startswith(compare_with.lower())
        return compare_with.lower() == search_elements.lower()
    if isinstance(search_elements, Collection):
        if isinstance(search_elements, dict):
            if (
                match_key := _get_search_key(
                    search_elements=search_elements, search_key=search_key
                )
                if search_key
                else None
            ):
                if (elements := search_elements.get(match_key)) is None:
                    return False
                search_elements = elements
        for element in search_elements:
            if do_wildcard_search:
                if compare_with.lower().startswith(element.lower()):
                    return True
            elif compare_with.lower() == element.lower():
                return True
    return False


def _get_search_key(search_elements: Collection[str], search_key: str) -> str | None:
    """Search for a matching key in a collection."""
    for element in search_elements:
        if search_key.startswith(element):
            return element
    return None


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
    data_type: HmSysvarType | None = None
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


def cleanup_cache_dirs(instance_name: str, storage_folder: str) -> None:
    """Clean up the used cached directories."""
    cache_dir = f"{storage_folder}/cache"
    files_to_delete = [FILE_DEVICES, FILE_PARAMSETS]

    def _delete_file(file_name: str) -> None:
        if os.path.exists(os.path.join(cache_dir, file_name)):
            os.unlink(os.path.join(cache_dir, file_name))

    for file_to_delete in files_to_delete:
        _delete_file(file_name=f"{instance_name}_{file_to_delete}")


@dataclass(slots=True)
class Channel:
    """dataclass for a device channel."""

    type: str
    address: str

    @property
    def no(self) -> int | None:
        """Return the channel no."""
        return get_channel_no(self.address)
