"""
Helper functions used within hahomematic
"""
from __future__ import annotations

import logging
import ssl
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    ATTR_HM_ALARM,
    ATTR_HM_LIST,
    ATTR_HM_LOGIC,
    ATTR_HM_NUMBER,
    ATTR_NAME,
    ATTR_TYPE,
    ATTR_VALUE,
    HA_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def generate_unique_id(
    address: str, parameter: str | None = None, prefix: str | None = None
) -> str:
    """
    Build unique id from address and parameter.
    """
    unique_id = address.replace(":", "_").replace("-", "_")
    if parameter:
        unique_id = f"{unique_id}_{parameter}"

    if prefix:
        unique_id = f"{prefix}_{unique_id}"

    return f"{HA_DOMAIN}_{unique_id}".lower()


def make_http_credentials(
    username: str | None = None, password: str | None = None
) -> str:
    """Build auth part for api_url."""
    credentials = ""
    if username is None:
        return credentials
    if username is not None:
        if ":" in username:
            return credentials
        credentials += username
    if credentials and password is not None:
        credentials += f":{password}"
    return f"{credentials}@"


def build_api_url(
    host: str,
    port: int,
    path: str | None,
    username: str | None = None,
    password: str | None = None,
    tls: bool = False,
) -> str:
    """Build XML-RPC API URL from components."""
    credentials = make_http_credentials(username, password)
    scheme = "http"
    if not path:
        path = ""
    if path and not path.startswith("/"):
        path = f"/{path}"
    if tls:
        scheme += "s"
    return f"{scheme}://{credentials}{host}:{port}{path}"


def parse_ccu_sys_var(data: dict[str, Any]) -> tuple[str, Any]:
    """Helper to parse type of system variables of CCU."""
    # pylint: disable=no-else-return
    if data[ATTR_TYPE] == ATTR_HM_LOGIC:
        return data[ATTR_NAME], data[ATTR_VALUE] == "true"
    if data[ATTR_TYPE] == ATTR_HM_ALARM:
        return data[ATTR_NAME], data[ATTR_VALUE] == "true"
    elif data[ATTR_TYPE] == ATTR_HM_NUMBER:
        return data[ATTR_NAME], float(data[ATTR_VALUE])
    elif data[ATTR_TYPE] == ATTR_HM_LIST:
        return data[ATTR_NAME], int(data[ATTR_VALUE])
    return data[ATTR_NAME], data[ATTR_VALUE]


def get_entity_name(
    central: hm_central.CentralUnit,
    address: str,
    parameter: str,
    unique_id: str,
) -> str:
    """generate name for entity"""
    name = central.names.get_name(address) or unique_id
    if name.count(":") == 1:
        d_name = name.split(":")[0]
        p_name = parameter.title().replace("_", " ")
        c_name = ""
        if central.paramsets.has_multiple_channels(
            address=address, parameter=parameter
        ):
            c_no = name.split(":")[1]
            c_name = "" if c_no == "0" else f" ch{c_no}"
        name = f"{d_name} {p_name}{c_name}"
    else:
        d_name = name
        p_name = parameter.title().replace("_", " ")
        name = f"{d_name} {p_name}"
    return name


def get_custom_entity_name(
    central: hm_central.CentralUnit,
    address: str,
    unique_id: str,
    channel_no: int | None = None,
) -> str:
    """generate name for entity"""
    if channel_no and ":" not in address:
        address = f"{address}:{channel_no}"

    return central.names.get_name(address) or unique_id


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
