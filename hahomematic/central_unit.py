"""
CentralUnit module.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
import json
import logging
import os
import threading
from typing import Any

from aiohttp import ClientSession

from hahomematic import config
import hahomematic.client as hm_client
from hahomematic.const import (
    ATTR_HM_ADDRESS,
    BACKEND_PYDEVCCU,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    DATA_NO_SAVE,
    DATA_SAVE_SUCCESS,
    DEFAULT_ENCODING,
    DEFAULT_PASSWORD,
    DEFAULT_TLS,
    DEFAULT_USERNAME,
    DEFAULT_VERIFY_TLS,
    FILE_DEVICES,
    FILE_NAMES,
    FILE_PARAMSETS,
    HM_VIRTUAL_REMOTE_HM,
    HM_VIRTUAL_REMOTE_HMIP,
    LOCALHOST,
    PRIMARY_PORTS,
    HmPlatform,
)
from hahomematic.data import INSTANCES
from hahomematic.device import HmDevice, create_devices
from hahomematic.entity import BaseEntity, GenericEntity
from hahomematic.helpers import get_device_address, get_device_channel
from hahomematic.hub import HmDummyHub, HmHub
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.proxy import NoConnection
import hahomematic.xml_rpc_server as xml_rpc

_LOGGER = logging.getLogger(__name__)


class CentralUnit:
    """Central unit that collects everything required to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig):
        _LOGGER.debug("CentralUnit.__init__")
        self.central_config: CentralConfig = central_config

        self.instance_name: str = self.central_config.name
        self.entry_id: str = self.central_config.entry_id
        self._available: bool = True
        self._loop: asyncio.AbstractEventLoop = self.central_config.loop
        self._xml_rpc_server: xml_rpc.XMLRPCServer = self.central_config.xml_rpc_server
        self._xml_rpc_server.register_central(self)
        self.enable_virtual_channels: bool = self.central_config.enable_virtual_channels
        self.host: str = self.central_config.host
        self.json_port: int | None = self.central_config.json_port
        self.password: str | None = self.central_config.password
        self.username: str | None = None
        if self.password is not None:
            self.username = self.central_config.username
        self.tls: bool = self.central_config.tls
        self.verify_tls: bool = self.central_config.verify_tls
        self.client_session: ClientSession | None = self.central_config.client_session

        # Caches for CCU data
        # {interface_id, {address, paramsets}}
        self.paramsets_cache: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}

        self.address_parameter_cache: dict[tuple[str, str], list[int]] = {}
        # {interface_id,  {address, name}}
        self.names_cache: dict[str, dict[str, str]] = {}
        # {interface_id, {counter, device}}
        self.devices_raw_cache: dict[str, list[dict[str, Any]]] = {}
        # {interface_id, client}
        self.clients: dict[str, hm_client.Client] = {}
        # {url, client}
        self.clients_by_init_url: dict[str, list[hm_client.Client]] = {}
        # {interface_id, {address, channel_address}}
        self.devices: dict[str, dict[str, Any]] = {}
        # {interface_id, {address, dev_descriptions}
        self.devices_raw_dict: dict[str, dict[str, Any]] = {}
        # {{channel_address, parameter}, event_handle}
        self.entity_event_subscriptions: dict[tuple[str, str], Any] = {}
        # {unique_id, entity}
        self.hm_entities: dict[str, BaseEntity] = {}
        # {device_address, device}
        self.hm_devices: dict[str, HmDevice] = {}

        self.last_events: dict[str, int] = {}

        # Signature: (name, *args)
        self.callback_system_event: Callable | None = None
        # Signature: (interface_id, address, value_key, value)
        self.callback_entity_event: Callable | None = None
        # Signature: (event_type, event_data)
        self.callback_ha_event: Callable | None = None

        self.json_rpc_session: JsonRpcAioHttpClient = JsonRpcAioHttpClient(
            central_config=self.central_config
        )

        INSTANCES[self.instance_name] = self
        self._load_caches()
        self.init_address_parameter_list()
        self._connection_checker = ConnectionChecker(self)
        self.hub: HmHub | HmDummyHub | None = None

    def create_hub(self) -> HmHub | HmDummyHub:
        """Create the hub."""
        hub: HmHub | HmDummyHub
        if self.model is BACKEND_PYDEVCCU:
            hub = HmDummyHub(self)
        else:
            hub = HmHub(
                self,
                use_entities=self.central_config.enable_sensors_for_system_variables,
            )
        return hub

    async def init_hub(self) -> None:
        """Init the hub."""
        self.hub = self.create_hub()
        if isinstance(self.hub, HmHub):
            await self.hub.fetch_data()

    def init_address_parameter_list(self) -> None:
        """Initialize an address/parameter list to identify if a parameter name exists is in multiple channels."""
        for device_paramsets in self.paramsets_cache.values():
            for address, paramsets in device_paramsets.items():
                if ":" not in address:
                    continue
                d_address = get_device_address(address)

                for paramset in paramsets.values():
                    for parameter in paramset:
                        if (d_address, parameter) not in self.address_parameter_cache:
                            self.address_parameter_cache[(d_address, parameter)] = []
                        self.address_parameter_cache[(d_address, parameter)].append(
                            get_device_channel(address)
                        )

    def has_multiple_channels(self, address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ":" not in address:
            return False
        if channels := self.address_parameter_cache.get(
            (get_device_address(address), parameter)
        ):
            return len(set(channels)) > 1
        return False

    @property
    def available(self) -> bool:
        """Return the availability of the central_unit."""
        return self._available

    @property
    def model(self) -> str | None:
        """Return the model of the backend."""
        if client := self.get_primary_client():
            return client.model
        return None

    @property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if client := self.get_primary_client():
            return client.version
        return None

    @property
    def local_ip(self) -> str:
        """Return the local ip of the xmlrpc_server."""
        return self._xml_rpc_server.local_ip

    @property
    def local_port(self) -> int:
        """Return the local port of the xmlrpc_server."""
        return self._xml_rpc_server.local_port

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Return the loop for async operations."""
        if not self._loop:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def _load_caches(self) -> None:
        try:
            self.load_devices_raw()
            self.load_paramsets()
            self.load_names()
            for interface_id, device_descriptions in self.devices_raw_cache.items():
                if interface_id not in self.paramsets_cache:
                    self.paramsets_cache[interface_id] = {}
                handle_device_descriptions(self, interface_id, device_descriptions)
        except json.decoder.JSONDecodeError:
            _LOGGER.warning("Failed to load caches.")
            self.clear_all()

    def create_devices(self) -> None:
        """Create the devices."""
        if not self.clients:
            raise Exception("No clients initialized. Not starting central_unit.")
        try:
            create_devices(self)
        except Exception as err:
            _LOGGER.exception("CentralUnit.init: Failed to create entities")
            raise Exception("entity-creation-error") from err

    async def stop(self) -> None:
        """
        then shut down our XML-RPC server.
        To stop the central_unit we de-init from the CCU / Homegear,
        """
        _LOGGER.info("CentralUnit.stop: Stop connection checker.")
        await self.stop_connection_checker()
        for name, client in self.clients.items():
            if await client.proxy_de_init():
                _LOGGER.info("CentralUnit.stop: Proxy de-initialized: %s", name)
            client.stop()

        _LOGGER.info(
            "CentralUnit.stop: Clearing existing clients. Please recreate them!"
        )
        self.clients.clear()
        self.clients_by_init_url.clear()

        # un-register this instance from XMLRPCServer
        self._xml_rpc_server.un_register_central(self)
        # un-register and stop XMLRPCServer, if possible
        await xml_rpc.un_register_xml_rpc_server()

        _LOGGER.debug("CentralUnit.stop: Removing instance")
        del INSTANCES[self.instance_name]

    def create_task(self, target: Awaitable) -> None:
        """Add task to the executor pool."""
        self.loop.call_soon_threadsafe(self.async_create_task, target)

    def async_create_task(self, target: Awaitable) -> asyncio.Task:
        """Create a task from within the event loop. This method must be run in the event loop."""
        return self.loop.create_task(target)

    def run_coroutine(self, coro: Coroutine) -> Any:
        """call coroutine from sync"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    async def async_add_executor_job(
        self, executor_func: Callable, *args: Any
    ) -> Awaitable:
        """Add an executor job from within the event loop."""
        return await self.loop.run_in_executor(None, executor_func, *args)

    def start_connection_checker(self) -> None:
        """Start the connection checker."""
        if self.model is not BACKEND_PYDEVCCU:
            self._connection_checker.start()

    async def stop_connection_checker(self) -> None:
        """Start the connection checker."""
        self._connection_checker.stop()

    async def is_connected(self) -> bool:
        """Check connection to ccu."""
        for client in self.clients.values():
            if not await client.is_connected():
                _LOGGER.warning(
                    "CentralUnit.is_connected: No connection to %s.", client.name
                )
                if self._available:
                    self.mark_all_devices_availability(False)
                    self._available = False
                return False
        if not self._available:
            self.mark_all_devices_availability(True)
            self._available = True
        return True

    async def reconnect(self) -> None:
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.warning(
                "CentralUnit.reconnect: re-connect to central_unit %s",
                self.instance_name,
            )
            for client in self.clients.values():
                await client.proxy_re_init()

    def mark_all_devices_availability(self, available: bool) -> None:
        """Mark all device's availability state."""
        for hm_device in self.hm_devices.values():
            hm_device.set_availability(available)

    async def get_all_system_variables(self) -> dict[str, Any] | None:
        """Get all system variables from CCU / Homegear."""
        if client := self.get_primary_client():
            return await client.get_all_system_variables()
        return None

    async def get_system_variable(self, name: str) -> Any | None:
        """Get system variable from CCU / Homegear."""
        if client := self.get_primary_client():
            return await client.get_system_variable(name)
        return None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        if client := self.get_primary_client():
            await client.set_system_variable(name, value)

    async def get_service_messages(self) -> list[list[tuple[str, str, Any]]]:
        """Get service messages from CCU / Homegear."""
        service_messages: list[list[tuple[str, str, Any]]] = []
        for client in self.clients.values():
            if client.port in PRIMARY_PORTS:
                if client_messages := await client.get_service_messages():
                    service_messages.append(client_messages)
        return _remove_dummy_service_message(service_messages)

    # pylint: disable=invalid-name
    async def set_install_mode(
        self,
        interface_id: str,
        on: bool = True,
        t: int = 60,
        mode: int = 1,
        address: str | None = None,
    ) -> None:
        """Activate or deactivate install-mode on CCU / Homegear."""
        if client := self.get_primary_client(interface_id):
            await client.set_install_mode(on=on, t=t, mode=mode, address=address)

    async def get_install_mode(self, interface_id: str) -> int:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        if client := self.get_primary_client(interface_id):
            return int(await client.get_install_mode())
        return 0

    async def put_paramset(
        self,
        interface_id: str,
        address: str,
        paramset: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set paramsets manually."""

        if client := self.get_primary_client(interface_id):
            await client.put_paramset(
                address=address, paramset=paramset, value=value, rx_mode=rx_mode
            )

    def _get_virtual_remote(self, address: str) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for client in self.clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.address == address:
                return virtual_remote
        return None

    async def press_virtual_remote_key(self, address: str, parameter: str) -> None:
        """Simulate a key press on the virtual remote."""
        if ":" not in address:
            _LOGGER.warning(
                "CentralUnit.press_virtual_remote_key: address is missing channel information."
            )

        if address.startswith(HM_VIRTUAL_REMOTE_HM.upper()):
            address = address.replace(
                HM_VIRTUAL_REMOTE_HM.upper(), HM_VIRTUAL_REMOTE_HM
            )
        if address.startswith(HM_VIRTUAL_REMOTE_HMIP.upper()):
            address = address.replace(
                HM_VIRTUAL_REMOTE_HMIP.upper(), HM_VIRTUAL_REMOTE_HMIP
            )

        if virtual_remote := self._get_virtual_remote(get_device_address(address)):
            if virtual_remote_channel := virtual_remote.action_events.get(
                (address, parameter)
            ):
                await virtual_remote_channel.send_value(True)

    def get_hm_entities_by_hmplatform(self, platform: HmPlatform) -> list[BaseEntity]:
        """
        Return all hm-entities by platform
        """
        hm_entities = []
        for entity in self.hm_entities.values():
            if entity and entity.platform == platform and entity.create_in_ha:
                hm_entities.append(entity)

        return hm_entities

    def get_primary_client(
        self, interface_id: str | None = None
    ) -> hm_client.Client | None:
        """Return the client by interface_id or the first with a primary port."""
        try:
            if interface_id:
                return self.clients[interface_id]
            for client in self.clients.values():
                if client.port in PRIMARY_PORTS:
                    return client

        except IndexError as err:
            message = (
                f"Can't resolve interface for {self.instance_name}: {interface_id}"
            )
            _LOGGER.warning(message)
            raise hm_client.ClientException(message) from err
        return None

    def get_hm_entity_by_parameter(
        self, address: str, parameter: str
    ) -> GenericEntity | None:
        """Get entity by address and parameter."""
        if ":" in address:
            if device := self.hm_devices.get(get_device_address(address)):
                if entity := device.entities.get((address, parameter)):
                    return entity
        return None

    def has_address(self, address: str) -> bool:
        """Check if address is handled by central_unit."""
        return self.hm_devices.get(get_device_address(address)) is not None

    def get_all_parameters(self) -> list[str]:
        """Return all parameters"""
        parameters: set[str] = set()
        for interface_id in self.paramsets_cache:
            for address in self.paramsets_cache[interface_id]:
                for paramset in self.paramsets_cache[interface_id][address].values():
                    parameters.update(paramset)

        return sorted(parameters)

    def get_parameters(self, address: str) -> list[str]:
        """Return all parameters of a device"""
        parameters: set[str] = set()
        for interface_id in self.paramsets_cache:
            for p_address in self.paramsets_cache[interface_id]:
                if p_address.startswith(address):
                    for paramset in self.paramsets_cache[interface_id][
                        p_address
                    ].values():
                        parameters.update(paramset)

        return sorted(parameters)

    def get_all_used_parameters(self) -> list[str]:
        """Return used parameters"""
        parameters: set[str] = set()
        for entity in self.hm_entities.values():
            if isinstance(entity, GenericEntity):
                if getattr(entity, "parameter", None):
                    parameters.add(entity.parameter)

        return sorted(parameters)

    def get_used_parameters(self, address: str) -> list[str]:
        """Return used parameters"""
        parameters: set[str] = set()
        if device := self.hm_devices.get(address):
            for entity in device.entities.values():
                if getattr(entity, "parameter", None):
                    parameters.add(entity.parameter)

        return sorted(parameters)

    async def save_devices_raw(self) -> Awaitable[int]:
        """
        Save current device data in DEVICES_RAW to disk.
        """

        def _save_devices_raw() -> int:
            if not check_cache_dir():
                return DATA_NO_SAVE
            with open(
                file=os.path.join(
                    config.CACHE_DIR, f"{self.instance_name}_{FILE_DEVICES}"
                ),
                mode="w",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                json.dump(self.devices_raw_cache, fptr)
            return DATA_SAVE_SUCCESS

        return await self.async_add_executor_job(_save_devices_raw)

    def load_devices_raw(self) -> int:
        """
        Load device data from disk into devices_raw.
        """
        if not check_cache_dir():
            return DATA_NO_LOAD
        if not os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_DEVICES}")
        ):
            return DATA_NO_LOAD
        with open(
            file=os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_DEVICES}"),
            mode="r",
            encoding=DEFAULT_ENCODING,
        ) as fptr:
            self.devices_raw_cache = json.load(fptr)
        return DATA_LOAD_SUCCESS

    def clear_devices_raw(self) -> None:
        """
        Remove stored device data from disk and clear devices_raw.
        """
        check_cache_dir()
        if os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_DEVICES}")
        ):
            os.unlink(
                os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_DEVICES}")
            )
        self.devices_raw_cache.clear()

    async def save_paramsets(self) -> Awaitable[int]:
        """
        Save current paramset data in PARAMSETS to disk.
        """

        def _save_paramsets() -> int:
            if not check_cache_dir():
                return DATA_NO_SAVE
            with open(
                file=os.path.join(
                    config.CACHE_DIR, f"{self.instance_name}_{FILE_PARAMSETS}"
                ),
                mode="w",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                json.dump(self.paramsets_cache, fptr)
            return DATA_SAVE_SUCCESS

        self.init_address_parameter_list()
        return await self.async_add_executor_job(_save_paramsets)

    def load_paramsets(self) -> int:
        """
        Load paramset data from disk into PARAMSETS.
        """
        if not check_cache_dir():
            return DATA_NO_LOAD
        if not os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_PARAMSETS}")
        ):
            return DATA_NO_LOAD
        with open(
            file=os.path.join(
                config.CACHE_DIR, f"{self.instance_name}_{FILE_PARAMSETS}"
            ),
            mode="r",
            encoding=DEFAULT_ENCODING,
        ) as fptr:
            self.paramsets_cache = json.load(fptr)
        return DATA_LOAD_SUCCESS

    def clear_paramsets(self) -> None:
        """
        Remove stored paramset data from disk.
        """
        check_cache_dir()
        if os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_PARAMSETS}")
        ):
            os.unlink(
                os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_PARAMSETS}")
            )
        self.paramsets_cache.clear()

    async def save_names(self) -> Awaitable[int]:
        """
        Save current name data in NAMES to disk.
        """

        def _save_names() -> int:
            if not check_cache_dir():
                return DATA_NO_SAVE
            with open(
                file=os.path.join(
                    config.CACHE_DIR, f"{self.instance_name}_{FILE_NAMES}"
                ),
                mode="w",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                json.dump(self.names_cache, fptr)
            return DATA_SAVE_SUCCESS

        return await self.async_add_executor_job(_save_names)

    def load_names(self) -> int:
        """
        Load name data from disk into NAMES.
        """
        if not check_cache_dir():
            return DATA_NO_LOAD
        if not os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_NAMES}")
        ):
            return DATA_NO_LOAD
        with open(
            file=os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_NAMES}"),
            mode="r",
            encoding=DEFAULT_ENCODING,
        ) as fptr:
            self.names_cache = json.load(fptr)
        return DATA_LOAD_SUCCESS

    def clear_names(self) -> None:
        """
        Remove stored names data from disk.
        """
        check_cache_dir()
        if os.path.exists(
            os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_NAMES}")
        ):
            os.unlink(
                os.path.join(config.CACHE_DIR, f"{self.instance_name}_{FILE_NAMES}")
            )
        self.names_cache.clear()

    def clear_all(self) -> None:
        """
        Clear all stored data.
        """
        self.clear_devices_raw()
        self.clear_paramsets()
        self.clear_names()


class ConnectionChecker(threading.Thread):
    """
    Periodically check Connection to CCU / Homegear.
    """

    def __init__(self, central: CentralUnit):
        threading.Thread.__init__(self)
        self._central = central
        self._active = True

    def run(self) -> None:
        """
        Run the central thread.
        """
        _LOGGER.info(
            "ConnectionCecker.run: Init connection checker to server %s",
            self._central.instance_name,
        )

        self._central.run_coroutine(self._check_connection())

    def stop(self) -> None:
        """
        To stop the ConnectionChecker.
        """
        self._active = False

    async def _check_connection(self) -> None:
        sleep_time = config.CONNECTION_CHECKER_INTERVAL
        while self._active:
            _LOGGER.debug(
                "ConnectionCecker.check_connection: Checking connection to server %s",
                self._central.instance_name,
            )
            try:
                if not await self._central.is_connected():
                    _LOGGER.warning(
                        "ConnectionCecker.check_connection: No connection to server %s",
                        self._central.instance_name,
                    )
                    await asyncio.sleep(sleep_time)
                    await self._central.reconnect()
                await asyncio.sleep(sleep_time)
            except NoConnection as nex:
                _LOGGER.exception("check_connection: no connection: %s", nex.args)
                await asyncio.sleep(sleep_time)
                continue
            except Exception:
                _LOGGER.exception("check_connection: Exception")


def check_cache_dir() -> bool:
    """Check presence of cache directory."""
    if not config.CACHE_DIR:
        return False
    if not os.path.exists(config.CACHE_DIR):
        os.makedirs(config.CACHE_DIR)
    return True


def handle_device_descriptions(
    central: CentralUnit, interface_id: str, dev_descriptions: list[dict[str, Any]]
) -> None:
    """
    Handle provided list of device descriptions.
    """
    if interface_id not in central.devices:
        central.devices[interface_id] = {}
    if interface_id not in central.devices_raw_dict:
        central.devices_raw_dict[interface_id] = {}
    for desc in dev_descriptions:
        address = desc[ATTR_HM_ADDRESS]
        central.devices_raw_dict[interface_id][address] = desc
        if ":" not in address and address not in central.devices[interface_id]:
            central.devices[interface_id][address] = {}
        if ":" in address:
            main = get_device_address(address)
            if main not in central.devices[interface_id]:
                central.devices[interface_id][main] = {}
            central.devices[interface_id][main][address] = {}


class CentralConfig:
    """Config for a Client."""

    def __init__(
        self,
        entry_id: str,
        loop: asyncio.AbstractEventLoop,
        xml_rpc_server: xml_rpc.XMLRPCServer,
        name: str,
        host: str = LOCALHOST,
        username: str = DEFAULT_USERNAME,
        password: str | None = DEFAULT_PASSWORD,
        tls: bool = DEFAULT_TLS,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        client_session: ClientSession | None = None,
        callback_host: str | None = None,
        callback_port: str | None = None,
        json_port: int | None = None,
        json_tls: bool = DEFAULT_TLS,
        enable_virtual_channels: bool = False,
        enable_sensors_for_system_variables: bool = False,
    ):
        self.entry_id = entry_id
        self.loop = loop
        self.xml_rpc_server = xml_rpc_server
        self.name = name
        self.host = host
        self.username = username
        self.password = password
        self.tls = tls
        self.verify_tls = verify_tls
        self.client_session = client_session
        self.callback_host = callback_host
        self.callback_port = callback_port
        self.json_port = json_port
        self.json_tls = json_tls
        self.enable_virtual_channels = enable_virtual_channels
        self.enable_sensors_for_system_variables = enable_sensors_for_system_variables

    def get_central(self) -> CentralUnit:
        """Identify the used client."""
        return CentralUnit(self)


def _remove_dummy_service_message(
    service_messages: list[list[tuple[str, str, Any]]]
) -> list[list[tuple[str, str, Any]]]:
    """Remove dummy SM, that hmip server always sends."""
    new_service_messages: list[list[tuple[str, str, Any]]] = []
    for client_messages in service_messages:
        if "0001D3C98DD4B6:3" not in [
            client_message[0] for client_message in client_messages
        ]:
            new_service_messages.append(client_messages)
    return new_service_messages
