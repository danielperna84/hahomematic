"""Helper functions used within hahomematic."""

from __future__ import annotations

import base64
from collections.abc import Collection
import contextlib
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
import logging
import os
import re
import socket
import ssl
import sys
from typing import Any, Final

from hahomematic.config import TIMEOUT
from hahomematic.const import (
    CACHE_PATH,
    CCU_PASSWORD_PATTERN,
    ENTITY_KEY,
    FILE_DEVICES,
    FILE_PARAMSETS,
    IDENTIFIER_SEPARATOR,
    INIT_DATETIME,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    SysvarType,
)
from hahomematic.exceptions import BaseHomematicException, HaHomematicException

_LOGGER: Final = logging.getLogger(__name__)


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


def check_config(
    central_name: str | None,
    username: str | None,
    password: str | None,
    storage_folder: str,
    extended_validation: bool = True,
) -> list[str]:
    """Check config. Throws BaseHomematicException on failure."""
    config_failures: list[str] = []
    if extended_validation and central_name and IDENTIFIER_SEPARATOR in central_name:
        config_failures.append(f"Instance name must not contain {IDENTIFIER_SEPARATOR}")
    if not username:
        config_failures.append("Username must not be empty")
    if password is None:
        config_failures.append("Password is required")
    if not check_password(password):
        config_failures.append("Password is not valid")
    try:
        check_or_create_directory(storage_folder)
    except BaseHomematicException as haex:
        config_failures.append(reduce_args(haex.args)[0])

    return config_failures


def delete_file(folder: str, file_name: str) -> None:
    """Delete the file."""
    file_path = os.path.join(folder, file_name)
    if (
        os.path.exists(folder)
        and os.path.exists(file_path)
        and (os.path.isfile(file_path) or os.path.islink(file_path))
    ):
        os.unlink(file_path)


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


def parse_sys_var(data_type: SysvarType | None, raw_value: Any) -> Any:
    """Parse system variables to fix type."""
    if not data_type:
        return raw_value
    if data_type in (SysvarType.ALARM, SysvarType.LOGIC):
        return to_bool(raw_value)
    if data_type == SysvarType.FLOAT:
        return float(raw_value)
    if data_type in (SysvarType.INTEGER, SysvarType.LIST):
        return int(raw_value)
    return raw_value


def to_bool(value: Any) -> bool:
    """Convert defined string values to bool."""
    if isinstance(value, bool):
        return value

    if not isinstance(value, str):
        raise TypeError("invalid literal for boolean. Not a string.")

    return value.lower() in ["y", "yes", "t", "true", "on", "1"]


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


def get_entity_key(channel_address: str, parameter: str) -> ENTITY_KEY:
    """Return an entity key."""
    return (str(channel_address), str(parameter))


@lru_cache(maxsize=2048)
def get_split_channel_address(channel_address: str) -> tuple[str, int | None]:
    """Return the device part of an address."""
    if ":" in channel_address:
        device_address, channel_no = channel_address.split(":")
        if channel_no in (None, "None"):
            return device_address, None
        return device_address, int(channel_no)
    return channel_address, None


def changed_within_seconds(last_change: datetime, max_age: int = MAX_CACHE_AGE) -> bool:
    """Entity has been modified within X minutes."""
    if last_change == INIT_DATETIME:
        return False
    delta = datetime.now() - last_change
    return delta.seconds < max_age


def find_free_port() -> int:
    """Find a free port for XmlRpc server default port."""
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("", 0))
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return int(sock.getsockname()[1])


def get_ip_addr(host: str, port: int) -> str | None:
    """Get local_ip from socket."""
    try:
        socket.gethostbyname(host)
    except Exception as exc:
        message = f"GET_LOCAL_IP: Can't resolve host for {host}:{port}"
        _LOGGER.warning(message)
        raise HaHomematicException(message) from exc
    tmp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tmp_socket.settimeout(TIMEOUT)
    tmp_socket.connect((host, port))
    local_ip = str(tmp_socket.getsockname()[0])
    tmp_socket.close()
    _LOGGER.debug("GET_LOCAL_IP: Got local ip: %s", local_ip)
    return local_ip


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
        if isinstance(search_elements, dict) and (
            match_key := _get_search_key(search_elements=search_elements, search_key=search_key)
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


def cleanup_cache_dirs(instance_name: str, storage_folder: str) -> None:
    """Clean up the used cached directories."""
    cache_dir = f"{storage_folder}/{CACHE_PATH}"
    files_to_delete = [FILE_DEVICES, FILE_PARAMSETS]

    for file_to_delete in files_to_delete:
        delete_file(folder=cache_dir, file_name=f"{instance_name}_{file_to_delete}")


@dataclass(frozen=True, kw_only=True, slots=True)
class Channel:
    """dataclass for a device channel."""

    type: str
    address: str

    @property
    def no(self) -> int | None:
        """Return the channel no."""
        return get_channel_no(self.address)


@dataclass(frozen=True, kw_only=True, slots=True)
class CacheEntry:
    """An entry for the value cache."""

    value: Any
    refresh_at: datetime

    @staticmethod
    def empty() -> CacheEntry:
        """Return empty cache entry."""
        return CacheEntry(value=NO_CACHE_ENTRY, refresh_at=datetime.min)

    @property
    def is_valid(self) -> bool:
        """Return if entry is valid."""
        if self.value == NO_CACHE_ENTRY:
            return False
        return changed_within_seconds(last_change=self.refresh_at)


def debug_enabled() -> bool:
    """Check if debug mode is enabled."""
    try:
        if sys.gettrace() is not None:
            return True
    except AttributeError:
        pass

    try:
        if sys.monitoring.get_tool(sys.monitoring.DEBUGGER_ID) is not None:
            return True
    except AttributeError:
        pass

    return False
