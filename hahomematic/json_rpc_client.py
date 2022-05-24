"""
Implementation of an async json-rpc client.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import re
import ssl
from typing import Any

from aiohttp import ClientConnectorError, ClientError, ClientSession, TCPConnector

from hahomematic import config
from hahomematic.const import (
    ATTR_ERROR,
    ATTR_NAME,
    ATTR_PASSWORD,
    ATTR_RESULT,
    ATTR_SESSION_ID,
    ATTR_USERNAME,
    DEFAULT_ENCODING,
    PATH_JSON_RPC,
    REGA_SCRIPT_FETCH_ALL_DEVICE_DATA,
    REGA_SCRIPT_GET_SERIAL,
    REGA_SCRIPT_PATH,
    REGA_SCRIPT_SET_SYSTEM_VARIABLE,
    SYSVAR_IS_INTERNAL,
    SYSVAR_MAX_VALUE,
    SYSVAR_MIN_VALUE,
    SYSVAR_NAME,
    SYSVAR_TYPE,
    SYSVAR_UNIT,
    SYSVAR_VALUE,
    SYSVAR_VALUE_LIST,
)
from hahomematic.exceptions import BaseHomematicException, HaHomematicException
from hahomematic.helpers import SystemVariableData, get_tls_context, parse_ccu_sys_var

_LOGGER = logging.getLogger(__name__)


class JsonRpcAioHttpClient:
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        username: str,
        password: str,
        device_url: str,
        client_session: ClientSession | None = None,
        tls: bool = False,
        verify_tls: bool = False,
    ):
        """Session setup."""
        if client_session:
            self._client_session = client_session
        else:
            conn = TCPConnector(limit=3)
            self._client_session = ClientSession(connector=conn, loop=loop)
        self._session_id: str | None = None
        self._last_session_id_refresh: datetime | None = None
        self._username: str = username
        self._password: str | None = password
        self._tls: bool = tls
        self._tls_context: ssl.SSLContext = get_tls_context(verify_tls)
        self._url = f"{device_url}{PATH_JSON_RPC}"

    @property
    def is_activated(self) -> bool:
        """If session exists, then it is activated."""
        return self._session_id is not None

    async def _login_or_renew(self) -> bool:
        """Renew JSON-RPC session or perform login."""
        if not self.is_activated:
            self._session_id = await self._do_login()
            self._last_session_id_refresh = datetime.now()
            return self._session_id is not None
        if self._session_id:
            self._session_id = await self._do_renew_login(self._session_id)
        return self._session_id is not None

    async def _do_renew_login(self, session_id: str) -> str | None:
        """Renew JSON-RPC session or perform login."""
        try:
            if self._updated_within_seconds():
                return session_id
            method = "Session.renew"
            response = await self._do_post(
                session_id=session_id,
                method=method,
                extra_params={ATTR_SESSION_ID: session_id},
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                if response[ATTR_RESULT] is True:
                    self._last_session_id_refresh = datetime.now()
                    _LOGGER.debug(
                        "_do_renew_login: Method: %s [%s]", method, session_id
                    )
                    return session_id
            return await self._do_login()
        except ClientError as cer:
            _LOGGER.error(
                "_do_renew_login: ClientError [%s] while renewing JSON-RPC session",
                cer.args,
            )
            return None

    def _updated_within_seconds(self, age_seconds: int = 90) -> bool:
        """Check if session id has been updated within 90 seconds."""
        if self._last_session_id_refresh is None:
            return False
        delta = datetime.now() - self._last_session_id_refresh
        if delta.seconds < age_seconds:
            return True
        return False

    async def _do_login(self) -> str | None:
        """Login to CCU and return session."""
        session_id: str | None = None
        try:
            if not self._username:
                _LOGGER.warning("_do_login: No username set.")
                return None
            if not self._password:
                _LOGGER.warning("_do_login: No password set.")
                return None

            params = {
                ATTR_USERNAME: self._username,
                ATTR_PASSWORD: self._password,
            }
            method = "Session.login"
            response = await self._do_post(
                session_id=False,
                method=method,
                extra_params=params,
                use_default_params=False,
            )
            if response[ATTR_ERROR] is None and response[ATTR_RESULT]:
                session_id = response[ATTR_RESULT]

            _LOGGER.debug("_do_login: Method: %s [%s]", method, session_id)

            if not session_id:
                _LOGGER.warning(
                    "_do_login: Unable to open session: %s", response[ATTR_ERROR]
                )
                return None
            return session_id
        except BaseHomematicException as hhe:
            _LOGGER.error(
                "_do_login: %s [%s] while logging in via JSON-RPC", hhe.name, hhe.args
            )
            return None

    async def _post(
        self,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if keep_session:
            await self._login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._do_login()

        if not session_id:
            _LOGGER.warning("_post: Error while logging in via JSON-RPC.")
            return {"error": "Unable to open session.", "result": {}}

        _LOGGER.debug("_post: Method: %s, [%s]", method, extra_params)
        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params=extra_params,
            use_default_params=use_default_params,
        )

        if not keep_session:
            await self._do_logout(session_id=session_id)
        if (error := response["error"]) is not None:
            raise HaHomematicException(f"post: error: {error}")
        return response

    async def _post_script(
        self,
        script_name: str,
        extra_params: dict[str, str] | None = None,
        keep_session: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST_SCRIPT function."""
        if keep_session:
            await self._login_or_renew()
            session_id = self._session_id
        else:
            session_id = await self._do_login()

        if not session_id:
            _LOGGER.warning("_post_script: Error while logging in via JSON-RPC.")
            return {"error": "Unable to open session.", "result": {}}

        script_file = os.path.join(
            Path(__file__).resolve().parent, REGA_SCRIPT_PATH, script_name
        )
        script = Path(script_file).read_text(encoding=DEFAULT_ENCODING)

        if extra_params:
            for variable, value in extra_params.items():
                script = script.replace(f"##{variable}##", value)

        method = "ReGa.runScript"
        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params={"script": script},
        )
        _LOGGER.debug("_post_script: Method: %s [%s]", method, script_name)

        if not keep_session:
            await self._do_logout(session_id=session_id)

        if (error := response["error"]) is not None:
            raise HaHomematicException(f"_post_script: error: {error}")
        return response

    async def _do_post(
        self,
        session_id: bool | str,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if not self._username:
            no_username = "_do_post: No username set."
            _LOGGER.warning(no_username)
            return {"error": str(no_username), "result": {}}
        if not self._password:
            no_password = "_do_post: No password set."
            _LOGGER.warning(no_password)
            return {"error": str(no_password), "result": {}}

        params = _get_params(session_id, extra_params, use_default_params)

        try:
            payload = json.dumps(
                {"method": method, "params": params, "jsonrpc": "1.1", "id": 0}
            ).encode("utf-8")

            headers = {
                "Content-Type": "application/json",
                "Content-Length": str(len(payload)),
            }

            if self._tls:
                response = await self._client_session.post(
                    self._url,
                    data=payload,
                    headers=headers,
                    timeout=config.TIMEOUT,
                    ssl=self._tls_context,
                )
            else:
                response = await self._client_session.post(
                    self._url, data=payload, headers=headers, timeout=config.TIMEOUT
                )
            if response.status == 200:
                try:
                    return await response.json(encoding="utf-8")
                except ValueError as ver:
                    _LOGGER.error(
                        "_do_post: ValueError [%s] Failed to parse JSON. Trying workaround",
                        ver.args,
                    )
                    # Workaround for bug in CCU
                    return json.loads(
                        (await response.json(encoding="utf-8")).replace("\\", "")
                    )
            else:
                _LOGGER.warning("_do_post: Status: %i", response.status)
                return {"error": response.status, "result": {}}
        except ClientConnectorError as err:
            _LOGGER.error("_do_post: ClientConnectorError")
            return {"error": str(err), "result": {}}
        except ClientError as cce:
            _LOGGER.error("_do_post: ClientError")
            return {"error": str(cce), "result": {}}
        except TypeError as ter:
            _LOGGER.error("_do_post: TypeError")
            return {"error": str(ter), "result": {}}
        except OSError as oer:
            _LOGGER.error("_do_post: OSError")
            return {"error": str(oer), "result": {}}
        except Exception as ex:
            raise HaHomematicException from ex

    async def logout(self) -> None:
        """Logout of CCU."""
        await self._do_logout(self._session_id)

    async def _do_logout(self, session_id: str | None) -> None:
        """Logout of CCU."""
        if not session_id:
            _LOGGER.debug("_do_logout: Not logged in. Not logging out.")
            return
        try:
            method = "Session.logout"
            params = {"_session_id_": session_id}
            response = await self._do_post(
                session_id=session_id,
                method=method,
                extra_params=params,
            )
            _LOGGER.debug("_do_logout: Method: %s [%s]", method, session_id)
            if response[ATTR_ERROR]:
                _LOGGER.warning("_do_logout: Logout error: %s", response[ATTR_RESULT])
        except ClientError as cer:
            _LOGGER.error(
                "logout: ClientError [%s] while logging in via JSON-RPC", cer.args
            )
        return

    def _has_credentials(self) -> bool:
        """Return if credentials are available."""
        return self._username is not None and self._password is not None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        _LOGGER.debug("set_system_variable: Setting System variable via JSON-RPC")
        try:
            params = {
                SYSVAR_NAME: name,
                SYSVAR_VALUE: value,
            }
            if isinstance(value, bool):
                params[SYSVAR_VALUE] = int(value)
                response = await self._post("SysVar.setBool", params)
            elif isinstance(value, str):
                if re.findall("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});", value):
                    _LOGGER.warning(
                        "set_system_variable: value (%s) contains html tags. This is not allowed.",
                        value,
                    )
                    return
                response = await self._post_script(
                    script_name=REGA_SCRIPT_SET_SYSTEM_VARIABLE, extra_params=params
                )
            else:
                response = await self._post("SysVar.setFloat", params)

            if json_result := response[ATTR_RESULT]:
                res = json_result
                _LOGGER.debug(
                    "set_system_variable: Result while setting variable: %s",
                    str(res),
                )
        except BaseHomematicException as hhe:
            _LOGGER.warning("set_system_variable: %s [%s]", hhe.name, hhe.args)

    async def delete_system_variable(self, name: str) -> None:
        """Delete a system variable from CCU / Homegear."""
        _LOGGER.debug("delete_system_variable: Getting System variable via JSON-RPC")
        try:
            params = {SYSVAR_NAME: name}
            response = await self._post(
                "SysVar.deleteSysVarByName",
                params,
            )
            if json_result := response[ATTR_RESULT]:
                deleted = json_result
                _LOGGER.debug("delete_system_variable: Deleted: %s", str(deleted))
        except BaseHomematicException as hhe:
            _LOGGER.warning("delete_system_variable: %s [%s]", hhe.name, hhe.args)

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        var = None
        _LOGGER.debug("get_system_variable: Getting System variable via JSON-RPC")
        try:
            params = {SYSVAR_NAME: name}
            response = await self._post(
                "SysVar.getValueByName",
                params,
            )
            if json_result := response[ATTR_RESULT]:
                # This does not yet support strings
                try:
                    var = float(json_result)
                except Exception:
                    var = json_result == "true"
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_system_variable: %s [%s]", hhe.name, hhe.args)

        return var

    async def get_all_system_variables(self) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        variables: list[SystemVariableData] = []
        _LOGGER.debug(
            "get_all_system_variables: Getting all system variables via JSON-RPC"
        )
        try:
            response = await self._post(
                "SysVar.getAll",
            )
            if json_result := response[ATTR_RESULT]:
                for var in json_result:
                    name = var[SYSVAR_NAME]
                    data_type = var[SYSVAR_TYPE]
                    raw_value = var[SYSVAR_VALUE]
                    unit = var[SYSVAR_UNIT]
                    internal = var[SYSVAR_IS_INTERNAL]
                    value_list: list[str] | None = None
                    if val_list := var.get(SYSVAR_VALUE_LIST):
                        value_list = val_list.split(";")
                    try:
                        value = parse_ccu_sys_var(
                            data_type=data_type, raw_value=raw_value
                        )
                        max_value = None
                        if raw_max_value := var.get(SYSVAR_MAX_VALUE):
                            max_value = parse_ccu_sys_var(
                                data_type=data_type, raw_value=raw_max_value
                            )
                        min_value = None
                        if raw_min_value := var.get(SYSVAR_MIN_VALUE):
                            min_value = parse_ccu_sys_var(
                                data_type=data_type, raw_value=raw_min_value
                            )
                        variables.append(
                            SystemVariableData(
                                name=name,
                                data_type=data_type,
                                unit=unit,
                                value=value,
                                value_list=value_list,
                                max_value=max_value,
                                min_value=min_value,
                                internal=internal,
                            )
                        )
                    except ValueError as verr:
                        _LOGGER.error(
                            "get_all_system_variables: ValueError [%s] Failed to parse SysVar %s ",
                            verr.args,
                            name,
                        )

        except BaseHomematicException as hhe:
            _LOGGER.warning("get_all_system_variables: %s [%s]", hhe.name, hhe.args)

        return variables

    async def get_all_channel_ids_room(self) -> dict[str, set[str]]:
        """Get all channel_ids per room from CCU / Homegear."""
        channel_ids_room: dict[str, set[str]] = {}
        _LOGGER.debug("get_all_channel_ids_per_room: Getting all rooms via JSON-RPC")
        try:
            response = await self._post(
                "Room.getAll",
            )
            if json_result := response[ATTR_RESULT]:
                for room in json_result:
                    if room["id"] not in channel_ids_room:
                        channel_ids_room[room["id"]] = set()
                    channel_ids_room[room["id"]].add(room["name"])
                    for channel_id in room["channelIds"]:
                        if channel_id not in channel_ids_room:
                            channel_ids_room[channel_id] = set()
                        channel_ids_room[channel_id].add(room["name"])
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_all_channel_ids_per_room: %s [%s]", hhe.name, hhe.args)

        return channel_ids_room

    async def get_all_channel_ids_function(self) -> dict[str, set[str]]:
        """Get all channel_ids per function from CCU / Homegear."""
        channel_ids_function: dict[str, set[str]] = {}
        _LOGGER.debug(
            "get_all_channel_ids_per_function: Getting all functions via JSON-RPC"
        )
        try:
            response = await self._post(
                "Subsection.getAll",
            )
            if json_result := response[ATTR_RESULT]:
                for function in json_result:
                    if function["id"] not in channel_ids_function:
                        channel_ids_function[function["id"]] = set()
                    channel_ids_function[function["id"]].add(function["name"])
                    for channel_id in function["channelIds"]:
                        if channel_id not in channel_ids_function:
                            channel_ids_function[channel_id] = set()
                        channel_ids_function[channel_id].add(function["name"])
        except BaseHomematicException as hhe:
            _LOGGER.warning(
                "get_all_channel_ids_per_function: %s [%s]", hhe.name, hhe.args
            )

        return channel_ids_function

    async def get_available_interfaces(self) -> list[str]:
        """Get all available interfaces from CCU / Homegear."""
        interfaces: list[str] = []
        _LOGGER.debug(
            "get_available_interfaces: Getting all available interfaces via JSON-RPC"
        )
        try:
            response = await self._post(
                "Interface.listInterfaces",
            )
            if json_result := response[ATTR_RESULT]:
                for interface in json_result:
                    interfaces.append(interface[ATTR_NAME])
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_available_interfaces: %s [%s]", hhe.name, hhe.args)

        return interfaces

    async def get_device_details(self) -> list[dict[str, Any]]:
        """Get the device details of the backend."""
        device_details = []

        _LOGGER.debug("get_device_details: Getting the device details via JSON-RPC")
        try:
            response = await self._post(
                method="Device.listAllDetail",
            )
            if json_result := response[ATTR_RESULT]:
                device_details = json_result
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_device_details: %s [%s]", hhe.name, hhe.args)

        return device_details

    async def get_all_device_data(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Get the all device data of the backend."""
        all_device_data: dict[str, Any] = {}

        _LOGGER.debug("get_all_device_data: Getting all device data via JSON-RPC")
        try:
            response = await self._post_script(
                script_name=REGA_SCRIPT_FETCH_ALL_DEVICE_DATA
            )
            if json_result := response[ATTR_RESULT]:
                all_device_data = json.loads(json_result)
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_all_device_data: %s [%s]", hhe.name, hhe.args)

        return _convert_to_values_cache(all_device_data)

    async def get_serial(self) -> str:
        """Get the serial of the backend."""
        serial = "unknown"

        _LOGGER.debug("get_serial: Getting the backend serial via JSON-RPC")
        try:
            response = await self._post_script(script_name=REGA_SCRIPT_GET_SERIAL)
            if json_result := response[ATTR_RESULT]:
                result = json.loads(json_result)
                serial = result["serial"]
                if len(serial) > 10:
                    serial = serial[-10:]
        except BaseHomematicException as hhe:
            _LOGGER.warning("get_serial: %s [%s]", hhe.name, hhe.args)

        return serial


def _get_params(
    session_id: bool | str,
    extra_params: dict[str, Any] | None,
    use_default_params: bool,
) -> dict[str, Any]:
    """Add additional params to default prams."""
    params: dict[str, Any] = {"_session_id_": session_id} if use_default_params else {}
    if extra_params:
        params.update(extra_params)
    return params


def _convert_to_values_cache(
    all_device_data: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Covert all device data o separated value list."""
    values_cache: dict[str, dict[str, dict[str, Any]]] = {}
    for device_adr, value in all_device_data.items():
        device_adr = device_adr.replace("%3A", ":")
        device_adrs = device_adr.split(".")
        interface = device_adrs[0]
        if interface not in values_cache:
            values_cache[interface] = {}
        channel_address = device_adrs[1]
        if channel_address not in values_cache[interface]:
            values_cache[interface][channel_address] = {}
        parameter = device_adrs[2]
        if parameter not in values_cache[interface][channel_address]:
            values_cache[interface][channel_address][parameter] = {}
        values_cache[interface][channel_address][parameter] = value
    return values_cache
