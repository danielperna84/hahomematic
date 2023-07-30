"""Implementation of an async json-rpc client."""
from __future__ import annotations

from datetime import datetime
import logging
import os
from pathlib import Path
import re
from typing import Any, Final

from aiohttp import (
    ClientConnectorCertificateError,
    ClientConnectorError,
    ClientError,
    ClientSession,
)
import orjson

from hahomematic import central_unit as hmcu, config
from hahomematic.const import (
    ATTR_NAME,
    ATTR_PASSWORD,
    ATTR_USERNAME,
    DEFAULT_ENCODING,
    MAX_JSON_SESSION_AGE,
    PATH_JSON_RPC,
    PROGRAM_ID,
    PROGRAM_ISACTIVE,
    PROGRAM_ISINTERNAL,
    PROGRAM_LASTEXECUTETIME,
    PROGRAM_NAME,
    REGA_SCRIPT_FETCH_ALL_DEVICE_DATA,
    REGA_SCRIPT_GET_SERIAL,
    REGA_SCRIPT_PATH,
    REGA_SCRIPT_SET_SYSTEM_VARIABLE,
    REGA_SCRIPT_SYSTEM_VARIABLES_EXT_MARKER,
    SYSVAR_HASEXTMARKER,
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_ID,
    SYSVAR_ISINTERNAL,
    SYSVAR_MAX_VALUE,
    SYSVAR_MIN_VALUE,
    SYSVAR_NAME,
    SYSVAR_TYPE,
    SYSVAR_TYPE_NUMBER,
    SYSVAR_UNIT,
    SYSVAR_VALUE,
    SYSVAR_VALUE_LIST,
)
from hahomematic.exceptions import ClientException
from hahomematic.support import (
    ProgramData,
    SystemVariableData,
    get_tls_context,
    parse_sys_var,
)

P_ERROR = "error"
P_RESULT = "result"
SESSION_ID: Final = "_session_id_"

ALLOWED_METHOD_ON_FAILURE = ("Session.login",)

_LOGGER = logging.getLogger(__name__)


class JsonRpcAioHttpClient:
    """Connection to CCU JSON-RPC Server."""

    def __init__(
        self,
        username: str,
        password: str,
        device_url: str,
        connection_state: hmcu.CentralConnectionState,
        client_session: ClientSession | None = None,
        tls: bool = False,
        verify_tls: bool = False,
    ) -> None:
        """Session setup."""
        self._client_session: Final = client_session
        self._connection_state: Final = connection_state
        self._username: Final = username
        self._password: Final = password
        self._tls: Final = tls
        self._tls_context: Final = get_tls_context(verify_tls) if tls else None
        self._url: Final = f"{device_url}{PATH_JSON_RPC}"
        self._script_cache: Final[dict[str, str]] = {}
        self._last_session_id_refresh: datetime | None = None
        self._session_id: str | None = None

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
        if self._updated_within_seconds():
            return session_id
        method = "Session.renew"
        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params={SESSION_ID: session_id},
        )

        if response[P_RESULT] and response[P_RESULT] is True:
            self._last_session_id_refresh = datetime.now()
            _LOGGER.debug("DO_RENEW_LOGIN: Method: %s [%s]", method, session_id)
            return session_id

        return await self._do_login()

    def _updated_within_seconds(self, max_age_seconds: int = MAX_JSON_SESSION_AGE) -> bool:
        """Check if session id has been updated within 90 seconds."""
        if self._last_session_id_refresh is None:
            return False
        delta = datetime.now() - self._last_session_id_refresh
        if delta.seconds < max_age_seconds:
            return True
        return False

    async def _do_login(self) -> str | None:
        """Login to CCU and return session."""
        if not self._has_credentials:
            _LOGGER.warning("DO_LOGIN failed: No credentials set")
            return None

        session_id: str | None = None

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

        _LOGGER.debug("DO_LOGIN: Method: %s [%s]", method, session_id)

        if result := response[P_RESULT]:
            session_id = result

        return session_id

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
            raise ClientException("Error while logging in")

        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params=extra_params,
            use_default_params=use_default_params,
        )

        if extra_params:
            _LOGGER.debug("POST method: %s, [%s]", method, extra_params)
        else:
            _LOGGER.debug("POST method: %s", method)

        if not keep_session:
            await self._do_logout(session_id=session_id)

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
            raise ClientException("Error while logging in")

        if (script := self._get_script(script_name=script_name)) is None:
            raise ClientException(f"Script file for {script_name} does not exist")

        if extra_params:
            for variable, value in extra_params.items():
                script = script.replace(f"##{variable}##", value)

        method = "ReGa.runScript"
        response = await self._do_post(
            session_id=session_id,
            method=method,
            extra_params={"script": script},
        )

        if not response[P_ERROR]:
            response[P_RESULT] = orjson.loads(response[P_RESULT])
        _LOGGER.debug("POST_SCRIPT: Method: %s [%s]", method, script_name)

        if not keep_session:
            await self._do_logout(session_id=session_id)

        return response

    def _get_script(self, script_name: str) -> str | None:
        """Return a script from the script cache. Load if required."""
        if script_name in self._script_cache:
            return self._script_cache[script_name]

        script_file = os.path.join(Path(__file__).resolve().parent, REGA_SCRIPT_PATH, script_name)
        if script := Path(script_file).read_text(encoding=DEFAULT_ENCODING):
            self._script_cache[script_name] = script
            return script
        return None

    async def _do_post(
        self,
        session_id: bool | str,
        method: str,
        extra_params: dict[str, str] | None = None,
        use_default_params: bool = True,
    ) -> dict[str, Any] | Any:
        """Reusable JSON-RPC POST function."""
        if not self._client_session:
            raise ClientException("ClientSession not initialized")
        if not self._has_credentials:
            raise ClientException("No credentials set")

        params = _get_params(session_id, extra_params, use_default_params)

        try:
            payload = orjson.dumps({"method": method, "params": params, "jsonrpc": "1.1", "id": 0})

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
                self._connection_state.remove_issue(issuer=self)
                try:
                    return await response.json(encoding="utf-8")
                except ValueError as ver:
                    _LOGGER.debug(
                        "DO_POST: ValueError [%s] Unable to parse JSON. Trying workaround",
                        ver.args,
                    )
                    # Workaround for bug in CCU
                    return orjson.loads((await response.json(encoding="utf-8")).replace("\\", ""))
            else:
                json_response = await response.json(encoding="utf-8")
                message = f"Status: {response.status}"
                if error := json_response[P_ERROR]:
                    message = f"{message}: {error}"
                raise ClientException(message)
        except ClientConnectorCertificateError as cccerr:
            message = f"ClientConnectorCertificateError[{cccerr}]"
            if self._tls is False and cccerr.ssl is True:
                message = (
                    f"{message}. Possible reason: 'Automatic forwarding to HTTPS' is enabled in backend, "
                    f"but this integration is not configured to use TLS"
                )
            raise ClientException(message) from cccerr
        except ClientConnectorError as err:
            raise ClientException from err
        except ClientError as cce:
            raise ClientException from cce
        except (OSError, TypeError, Exception) as ex:
            raise ClientException from ex

    async def logout(self) -> None:
        """Logout of CCU."""
        try:
            await self._do_logout(self._session_id)
        except ClientException as clex:
            self._handle_client_exception(method="LOGOUT", clex=clex)
            return

    async def _do_logout(self, session_id: str | None) -> None:
        """Logout of CCU."""
        if not session_id:
            _LOGGER.debug("DO_LOGOUT: Not logged in. Not logging out.")
            return

        method = "Session.logout"
        params = {SESSION_ID: session_id}
        await self._do_post(
            session_id=session_id,
            method=method,
            extra_params=params,
        )
        _LOGGER.debug("DO_LOGOUT: Method: %s [%s]", method, session_id)

    @property
    def _has_credentials(self) -> bool:
        """Return if credentials are available."""
        return self._username is not None and self._username != "" and self._password is not None

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""
        params = {
            PROGRAM_ID: pid,
        }
        try:
            response = await self._post("Program.execute", params)
            _LOGGER.debug("EXECUTE_PROGRAM: Executing a program")

            if json_result := response[P_RESULT]:
                _LOGGER.debug(
                    "EXECUTE_PROGRAM: Result while executing program: %s",
                    str(json_result),
                )
        except ClientException as clex:
            self._handle_client_exception(method="EXECUTE_PROGRAM", clex=clex)
            return False

        return True

    async def set_system_variable(self, name: str, value: Any) -> bool:
        """Set a system variable on CCU / Homegear."""

        params = {
            SYSVAR_NAME: name,
            SYSVAR_VALUE: value,
        }
        try:
            if isinstance(value, bool):
                params[SYSVAR_VALUE] = int(value)
                response = await self._post("SysVar.setBool", params)
            elif isinstance(value, str):
                if re.findall("<.*?>|&([a-z0-9]+|#[0-9]{1,6}|#x[0-9a-f]{1,6});", value):
                    _LOGGER.warning(
                        "SET_SYSTEM_VARIABLE failed: "
                        "Value (%s) contains html tags. This is not allowed",
                        value,
                    )
                    return False
                response = await self._post_script(
                    script_name=REGA_SCRIPT_SET_SYSTEM_VARIABLE, extra_params=params
                )
            else:
                response = await self._post("SysVar.setFloat", params)

            _LOGGER.debug("SET_SYSTEM_VARIABLE: Setting System variable")
            if json_result := response[P_RESULT]:
                _LOGGER.debug(
                    "SET_SYSTEM_VARIABLE: Result while setting variable: %s",
                    str(json_result),
                )
        except ClientException as clex:
            self._handle_client_exception(method="SET_SYSTEM_VARIABLE failed", clex=clex)
            return False

        return True

    async def delete_system_variable(self, name: str) -> bool:
        """Delete a system variable from CCU / Homegear."""
        params = {SYSVAR_NAME: name}
        try:
            response = await self._post(
                "SysVar.deleteSysVarByName",
                params,
            )

            _LOGGER.debug("DELETE_SYSTEM_VARIABLE: Getting System variable")
            if json_result := response[P_RESULT]:
                deleted = json_result
                _LOGGER.debug("DELETE_SYSTEM_VARIABLE: Deleted: %s", str(deleted))
        except ClientException as clex:
            self._handle_client_exception(method="DELETE_SYSTEM_VARIABLE", clex=clex)
            return False

        return True

    async def get_system_variable(self, name: str) -> Any:
        """Get single system variable from CCU / Homegear."""
        var = None

        try:
            params = {SYSVAR_NAME: name}
            response = await self._post(
                "SysVar.getValueByName",
                params,
            )

            _LOGGER.debug("GET_SYSTEM_VARIABLE: Getting System variable")
            if json_result := response[P_RESULT]:
                # This does not yet support strings
                try:
                    var = float(json_result)
                except Exception:
                    var = json_result == "true"
        except ClientException as clex:
            self._handle_client_exception(method="DELETE_SYSTEM_VARIABLE", clex=clex)
            return None

        return var

    async def get_all_system_variables(self, include_internal: bool) -> list[SystemVariableData]:
        """Get all system variables from CCU / Homegear."""
        variables: list[SystemVariableData] = []
        try:
            response = await self._post(
                "SysVar.getAll",
            )

            _LOGGER.debug("GET_ALL_SYSTEM_VARIABLES: Getting all system variables")
            if json_result := response[P_RESULT]:
                ext_markers = await self._get_system_variables_ext_markers()
                for var in json_result:
                    is_internal = var[SYSVAR_ISINTERNAL]
                    if include_internal is False and is_internal is True:
                        continue
                    var_id = var[SYSVAR_ID]
                    name = var[SYSVAR_NAME]
                    org_data_type = var[SYSVAR_TYPE]
                    raw_value = var[SYSVAR_VALUE]
                    if org_data_type == SYSVAR_TYPE_NUMBER:
                        data_type = (
                            SYSVAR_HM_TYPE_FLOAT if "." in raw_value else SYSVAR_HM_TYPE_INTEGER
                        )
                    else:
                        data_type = org_data_type
                    extended_sysvar = ext_markers.get(var_id, False)
                    unit = var[SYSVAR_UNIT]
                    value_list: list[str] | None = None
                    if val_list := var.get(SYSVAR_VALUE_LIST):
                        value_list = val_list.split(";")
                    try:
                        value = parse_sys_var(data_type=data_type, raw_value=raw_value)
                        max_value = None
                        if raw_max_value := var.get(SYSVAR_MAX_VALUE):
                            max_value = parse_sys_var(data_type=data_type, raw_value=raw_max_value)
                        min_value = None
                        if raw_min_value := var.get(SYSVAR_MIN_VALUE):
                            min_value = parse_sys_var(data_type=data_type, raw_value=raw_min_value)
                        variables.append(
                            SystemVariableData(
                                name=name,
                                data_type=data_type,
                                unit=unit,
                                value=value,
                                value_list=value_list,
                                max_value=max_value,
                                min_value=min_value,
                                extended_sysvar=extended_sysvar,
                            )
                        )
                    except ValueError as verr:
                        _LOGGER.warning(
                            "GET_ALL_SYSTEM_VARIABLES failed: "
                            "ValueError [%s] Failed to parse SysVar %s ",
                            verr.args,
                            name,
                        )
        except ClientException as clex:
            self._handle_client_exception(method="GET_ALL_SYSTEM_VARIABLES", clex=clex)
            return []

        return variables

    async def _get_system_variables_ext_markers(self) -> dict[str, Any]:
        """Get all system variables from CCU / Homegear."""
        ext_markers: dict[str, Any] = {}

        response = await self._post_script(script_name=REGA_SCRIPT_SYSTEM_VARIABLES_EXT_MARKER)

        _LOGGER.debug("GET_SYSTEM_VARIABLES_EXT_MARKERS: Getting system variables ext markers")
        if json_result := response[P_RESULT]:
            for data in json_result:
                ext_markers[data[SYSVAR_ID]] = data[SYSVAR_HASEXTMARKER]

        return ext_markers

    async def get_all_channel_ids_room(self) -> dict[str, set[str]]:
        """Get all channel_ids per room from CCU / Homegear."""
        channel_ids_room: dict[str, set[str]] = {}

        try:
            response = await self._post(
                "Room.getAll",
            )

            _LOGGER.debug("GET_ALL_CHANNEL_IDS_PER_ROOM: Getting all rooms")
            if json_result := response[P_RESULT]:
                for room in json_result:
                    if room["id"] not in channel_ids_room:
                        channel_ids_room[room["id"]] = set()
                    channel_ids_room[room["id"]].add(room["name"])
                    for channel_id in room["channelIds"]:
                        if channel_id not in channel_ids_room:
                            channel_ids_room[channel_id] = set()
                        channel_ids_room[channel_id].add(room["name"])
        except ClientException as clex:
            self._handle_client_exception(method="GET_ALL_CHANNEL_IDS_PER_ROOM", clex=clex)
            return {}

        return channel_ids_room

    async def get_all_channel_ids_function(self) -> dict[str, set[str]]:
        """Get all channel_ids per function from CCU / Homegear."""
        channel_ids_function: dict[str, set[str]] = {}

        try:
            response = await self._post(
                "Subsection.getAll",
            )

            _LOGGER.debug("GET_ALL_CHANNEL_IDS_PER_FUNCTION: Getting all functions")
            if json_result := response[P_RESULT]:
                for function in json_result:
                    if function["id"] not in channel_ids_function:
                        channel_ids_function[function["id"]] = set()
                    channel_ids_function[function["id"]].add(function["name"])
                    for channel_id in function["channelIds"]:
                        if channel_id not in channel_ids_function:
                            channel_ids_function[channel_id] = set()
                        channel_ids_function[channel_id].add(function["name"])
        except ClientException as clex:
            self._handle_client_exception(method="GET_ALL_CHANNEL_IDS_PER_FUNCTION", clex=clex)
            return {}

        return channel_ids_function

    async def get_available_interfaces(self) -> list[str]:
        """Get all available interfaces from CCU / Homegear."""
        interfaces: list[str] = []

        try:
            response = await self._post(
                "Interface.listInterfaces",
            )

            _LOGGER.debug("GET_AVAILABLE_INTERFACES: Getting all available interfaces")
            if json_result := response[P_RESULT]:
                for interface in json_result:
                    interfaces.append(interface[ATTR_NAME])
        except ClientException as clex:
            self._handle_client_exception(method="GET_AVAILABLE_INTERFACES", clex=clex)
            return []

        return interfaces

    async def get_device_details(self) -> list[dict[str, Any]]:
        """Get the device details of the backend."""
        device_details: list[dict[str, Any]] = []

        try:
            response = await self._post(
                method="Device.listAllDetail",
            )

            _LOGGER.debug("GET_DEVICE_DETAILS: Getting the device details")
            if json_result := response[P_RESULT]:
                device_details = json_result
        except ClientException as clex:
            self._handle_client_exception(method="GET_DEVICE_DETAILS", clex=clex)
            return []

        return device_details

    async def get_all_device_data(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Get the all device data of the backend."""
        all_device_data: dict[str, dict[str, dict[str, Any]]] = {}

        try:
            response = await self._post_script(script_name=REGA_SCRIPT_FETCH_ALL_DEVICE_DATA)

            _LOGGER.debug("GET_ALL_DEVICE_DATA: Getting all device data")
            if json_result := response[P_RESULT]:
                all_device_data = _convert_to_values_cache(json_result)
        except ClientException as clex:
            self._handle_client_exception(method="GET_ALL_DEVICE_DATA", clex=clex)
            return {}

        return all_device_data

    async def get_all_programs(self, include_internal: bool) -> list[ProgramData]:
        """Get the all programs of the backend."""
        all_programs: list[ProgramData] = []

        try:
            response = await self._post(
                method="Program.getAll",
            )

            _LOGGER.debug("GET_ALL_PROGRAMS: Getting all programs")
            if json_result := response[P_RESULT]:
                for prog in json_result:
                    is_internal = prog[PROGRAM_ISINTERNAL]
                    if include_internal is False and is_internal is True:
                        continue
                    pid = prog[PROGRAM_ID]
                    name = prog[PROGRAM_NAME]
                    is_active = prog[PROGRAM_ISACTIVE]
                    last_execute_time = prog[PROGRAM_LASTEXECUTETIME]

                    all_programs.append(
                        ProgramData(
                            pid=pid,
                            name=name,
                            is_active=is_active,
                            is_internal=is_internal,
                            last_execute_time=last_execute_time,
                        )
                    )
        except ClientException as clex:
            self._handle_client_exception(method="GET_ALL_PROGRAMS", clex=clex)
            return []

        return all_programs

    async def get_auth_enabled(self) -> bool | None:
        """Get the auth_enabled flag of the backend."""
        auth_enabled: bool | None = None

        try:
            response = await self._post(method="CCU.getAuthEnabled")

            _LOGGER.debug("GET_AUTH_ENABLED: Getting the flag auth_enabled")
            if (json_result := response[P_RESULT]) is not None:
                auth_enabled = bool(json_result)
        except ClientException as clex:
            self._handle_client_exception(method="GET_AUTH_ENABLED", clex=clex)
            return None
        return auth_enabled

    async def get_https_redirect_enabled(self) -> bool | None:
        """Get the auth_enabled flag of the backend."""
        https_redirect_enabled: bool | None = None

        try:
            response = await self._post(method="CCU.getHttpsRedirectEnabled")

            _LOGGER.debug("GET_HTTPS_REDIRECT_ENABLED: Getting the flag https_redirect_enabled")
            if (json_result := response[P_RESULT]) is not None:
                https_redirect_enabled = bool(json_result)
        except ClientException as clex:
            self._handle_client_exception(method="GET_HTTPS_REDIRECT_ENABLED", clex=clex)
            return None

        return https_redirect_enabled

    async def get_serial(self) -> str:
        """Get the serial of the backend."""
        serial = "unknown"

        try:
            response = await self._post_script(script_name=REGA_SCRIPT_GET_SERIAL)

            _LOGGER.debug("GET_SERIAL: Getting the backend serial")
            if json_result := response[P_RESULT]:
                serial = json_result["serial"]
                if len(serial) > 10:
                    serial = serial[-10:]
        except ClientException as clex:
            self._handle_client_exception(method="GET_SERIAL", clex=clex)
            return serial

        return serial

    def _handle_client_exception(self, method: str, clex: ClientException) -> None:
        """Handle ClientException."""
        if self._connection_state.json_issue:
            _LOGGER.debug("%s failed: %s [%s]", method, clex.name, clex.args)
        else:
            self._connection_state.add_issue(issuer=self)
            _LOGGER.error("%s failed: %s [%s]", method, clex.name, clex.args)


def _get_params(
    session_id: bool | str,
    extra_params: dict[str, Any] | None,
    use_default_params: bool,
) -> dict[str, Any]:
    """Add additional params to default prams."""
    params: dict[str, Any] = {SESSION_ID: session_id} if use_default_params else {}
    if extra_params:
        params.update(extra_params)
    return params


def _convert_to_values_cache(
    all_device_data: dict[str, Any]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Convert all device data o separated value list."""
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
