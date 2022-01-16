"""
CentralUnit module.
"""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from datetime import datetime
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
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_NEW_DEVICES,
    LOCALHOST,
    MANUFACTURER,
)
import hahomematic.data as hm_data
from hahomematic.decorators import callback_system_event
from hahomematic.device import HmDevice, create_devices
from hahomematic.entity import BaseEntity, GenericEntity
from hahomematic.exceptions import HaHomematicException, NoConnection
from hahomematic.helpers import (
    check_or_create_directory,
    get_device_address,
    get_device_channel,
)
from hahomematic.hub import HmDummyHub, HmHub
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
import hahomematic.xml_rpc_server as xml_rpc

_LOGGER = logging.getLogger(__name__)


class CentralUnit:
    """Central unit that collects everything required to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig):
        _LOGGER.debug("CentralUnit.__init__")
        self.central_config: CentralConfig = central_config
        self._domain = self.central_config.domain

        self.instance_name: str = self.central_config.name
        self._available: bool = True
        self._loop: asyncio.AbstractEventLoop = self.central_config.loop
        self._xml_rpc_server: xml_rpc.XmlRpcServer = self.central_config.xml_rpc_server
        self._xml_rpc_server.register_central(self)
        self._model: str | None = None

        # Caches for CCU data
        self.paramsets: ParamsetCache = ParamsetCache(central=self)
        self.names: NamesCache = NamesCache(central=self)
        self.raw_devices: RawDevicesCache = RawDevicesCache(central=self)
        self.rooms: RoomCache = RoomCache(central=self)

        # {interface_id, client}
        self._clients: dict[str, hm_client.Client] = {}
        # {url, client}
        self._clients_by_init_url: dict[str, list[hm_client.Client]] = {}

        # {{channel_address, parameter}, event_handle}
        self.entity_event_subscriptions: dict[tuple[str, str], Any] = {}
        # {unique_id, entity}
        self.hm_entities: dict[str, BaseEntity] = {}
        # {device_address, device}
        self.hm_devices: dict[str, HmDevice] = {}

        self.last_events: dict[str, datetime] = {}

        # Signature: (name, *args)
        self.callback_system_event: Callable | None = None
        # Signature: (interface_id, channel_address, value_key, value)
        self.callback_entity_event: Callable | None = None
        # Signature: (event_type, event_data)
        self.callback_ha_event: Callable | None = None

        self._json_rpc_session: JsonRpcAioHttpClient = JsonRpcAioHttpClient(
            central_config=self.central_config
        )

        hm_data.INSTANCES[self.instance_name] = self
        self._connection_checker = ConnectionChecker(self)
        self.hub: HmHub | HmDummyHub | None = None

    @property
    def domain(self) -> str:
        """Return the domain."""
        return self._domain

    def create_hub(self) -> HmHub | HmDummyHub:
        """Create the hub."""
        hub: HmHub | HmDummyHub
        if self.model is BACKEND_PYDEVCCU:
            hub = HmDummyHub(central=self)
        else:
            hub = HmHub(central=self)
        return hub

    async def init_hub(self) -> None:
        """Init the hub."""
        self.hub = self.create_hub()
        if isinstance(self.hub, HmHub):
            await self.hub.fetch_data()

    @property
    def available(self) -> bool:
        """Return the availability of the central_unit."""
        return self._available

    @property
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model:
            if client := self.get_client():
                self._model = client.model
        return self._model

    @property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if client := self.get_client():
            return client.version
        return None

    @property
    def device_url(self) -> str:
        """Return the device_url of the backend."""
        return self.central_config.device_url

    @property
    def device_info(self) -> dict[str, Any]:
        """Return central specific attributes."""
        return {
            "identifiers": {(self._domain, self.instance_name)},
            "name": self.instance_name,
            "manufacturer": MANUFACTURER,
            "model": self.model,
            "sw_version": self.version,
            "device_url": self.device_url,
        }

    @property
    def local_ip(self) -> str:
        """Return the local ip of the xmlrpc_server."""
        return self._xml_rpc_server.local_ip

    @property
    def local_port(self) -> int:
        """Return the local port of the xmlrpc_server."""
        return self._xml_rpc_server.local_port

    @property
    def json_rpc_session(self) -> JsonRpcAioHttpClient:
        """Return the json_rpc_session."""
        return self._json_rpc_session

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Return the loop for async operations."""
        if not self._loop:
            self._loop = asyncio.get_running_loop()
        return self._loop

    @property
    def clients(self) -> dict[str, hm_client.Client]:
        """Return the clients list."""
        return self._clients

    def get_client_by_interface_id(self, interface_id: str) -> hm_client.Client | None:
        """Return a client by interface_id."""
        return self._clients.get(interface_id)

    def get_clients_by_init_url(self, init_url: str) -> list[hm_client.Client]:
        """Return a client by init url."""
        return self._clients_by_init_url.get(init_url, [])

    def get_client(self) -> hm_client.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        client: hm_client.Client | None = None
        for client in self._clients.values():
            if client.get_virtual_remote():
                return client
        return client

    def has_client(self, interface_id: str) -> bool:
        """Check if client exists in central."""
        return self._clients.get(interface_id) is not None

    async def load_caches(self) -> None:
        """Load files to caches."""
        try:
            await self.raw_devices.load()
            await self.paramsets.load()
            await self.names.load()
        except json.decoder.JSONDecodeError:
            _LOGGER.warning("Failed to load caches.")
            await self.clear_all()

    def _create_devices(self) -> None:
        """Create the devices."""
        if not self._clients:
            raise Exception("No clients initialized. Not starting central_unit.")
        try:
            create_devices(self)
        except Exception as err:
            _LOGGER.exception("CentralUnit.init: Failed to create entities")
            raise Exception("entity-creation-error") from err

    async def delete_device(self, interface_id: str, device_address: str) -> None:
        """Delete devices from central_unit."""
        _LOGGER.debug(
            "CentralUnit.delete_device: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if (hm_device := self.hm_devices.get(device_address)) is None:
            return
        addresses: list[str] = hm_device.channels
        addresses.append(device_address)
        if len(addresses) == 0:
            _LOGGER.debug(
                "CentralUnit.delete_device: Nothing to delete: interface_id = %s, device_address = %s",
                interface_id,
                device_address,
            )
            return

        await self.delete_devices(interface_id, addresses)

    @callback_system_event(HH_EVENT_DELETE_DEVICES)
    async def delete_devices(self, interface_id: str, addresses: list[str]) -> None:
        """Delete devices from central_unit."""
        _LOGGER.debug(
            "CentralUnit.delete_devices: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )

        await self.raw_devices.cleanup(
            interface_id=interface_id, deleted_addresses=addresses
        )

        for address in addresses:
            try:
                if ":" in address:
                    self.paramsets.remove(
                        interface_id=interface_id, channel_address=address
                    )
                self.names.remove(address=address)
                if hm_device := self.hm_devices.get(address):
                    hm_device.remove_event_subscriptions()
                    hm_device.remove_from_collections()
                    del self.hm_devices[address]
            except KeyError:
                _LOGGER.exception("Failed to delete: %s", address)
        await self.paramsets.save()
        await self.names.save()

    @callback_system_event(HH_EVENT_NEW_DEVICES)
    async def add_new_devices(
        self, interface_id: str, dev_descriptions: list[dict[str, Any]]
    ) -> None:
        """Add new devices to central unit."""
        _LOGGER.debug(
            "CentralUnit.add_new_devices: interface_id = %s, dev_descriptions = %s",
            interface_id,
            len(dev_descriptions),
        )

        if interface_id not in self._clients:
            _LOGGER.error(
                "CentralUnit.add_new_devices: Missing client for interface_id %s.",
                interface_id,
            )
            return None

        # We need this list to avoid adding duplicates.
        known_addresses = [
            dev_desc[ATTR_HM_ADDRESS]
            for dev_desc in self.raw_devices.get_device_descriptions(interface_id)
        ]
        client = self._clients[interface_id]
        for dev_desc in dev_descriptions:
            try:
                if dev_desc[ATTR_HM_ADDRESS] not in known_addresses:
                    self.raw_devices.add_device_description(interface_id, dev_desc)
                    await client.fetch_paramsets(dev_desc)
            except Exception:
                _LOGGER.exception("CentralUnit.add_new_devices: Exception")
        await self.raw_devices.save()
        await self.paramsets.save()
        await client.fetch_names()
        await self.names.save()
        create_devices(self)

    async def stop(self) -> None:
        """
        then shut down our XML-RPC server.
        To stop the central_unit we de-init from the CCU / Homegear,
        """
        _LOGGER.info("CentralUnit.stop: Stop connection checker.")
        self.stop_connection_checker()
        for name, client in self._clients.items():
            if await client.proxy_de_init():
                _LOGGER.info("CentralUnit.stop: Proxy de-initialized: %s", name)
            client.stop()

        _LOGGER.info(
            "CentralUnit.stop: Clearing existing clients. Please recreate them!"
        )
        self._clients.clear()
        self._clients_by_init_url.clear()

        # un-register this instance from XMLRPCServer
        self._xml_rpc_server.un_register_central(central=self)
        # un-register and stop XMLRPCServer, if possible
        xml_rpc.un_register_xml_rpc_server()

        _LOGGER.debug("CentralUnit.stop: Removing instance")
        del hm_data.INSTANCES[self.instance_name]

    async def create_clients(self, client_configs: set[hm_client.ClientConfig]) -> None:
        """Create clients for the central unit. Start connection checker afterwards"""

        for client_config in client_configs:
            try:
                if client := await client_config.get_client():
                    _LOGGER.debug(
                        "CentralUnit.create_clients: Adding client %s to central.",
                        client.interface_id,
                    )
                    self._clients[client.interface_id] = client

                    if client.init_url not in self._clients_by_init_url:
                        self._clients_by_init_url[client.init_url] = []
                    self._clients_by_init_url[client.init_url].append(client)
                await self.rooms.load()
                self._create_devices()
            except HaHomematicException as ex:
                _LOGGER.debug(
                    "CentralUnit.create_clients: Failed to create interface %s to central. (%s)",
                    client_config.name,
                    ex.args,
                )

    async def init_clients(self) -> None:
        """Init clients of control unit, and start connection checker."""
        for client in self._clients.values():
            await client.proxy_init()

        self._start_connection_checker()

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

    def _start_connection_checker(self) -> None:
        """Start the connection checker."""
        if self.model is not BACKEND_PYDEVCCU:
            self._connection_checker.start()

    def stop_connection_checker(self) -> None:
        """Start the connection checker."""
        self._connection_checker.stop()

    async def is_connected(self) -> bool:
        """Check connection to ccu."""
        for client in self._clients.values():
            if not await client.is_connected():
                _LOGGER.warning(
                    "CentralUnit.is_connected: No connection to %s.", client.name
                )
                if self._available:
                    self.mark_all_devices_availability(available=False)
                    self._available = False
                return False
        if not self._available:
            self.mark_all_devices_availability(available=True)
            self._available = True
        return True

    async def reconnect(self, force_immediate: bool = False) -> None:
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.warning(
                "CentralUnit.reconnect: re-connect to central_unit %s",
                self.instance_name,
            )
            if not force_immediate:
                _LOGGER.info(
                    "CentralUnit.reconnect: waiting to re-connect to central_unit %s for %i s",
                    self.instance_name, int(config.RECONNECT_WAIT)
                )
                await asyncio.sleep(config.RECONNECT_WAIT)
            for client in self._clients.values():
                await client.proxy_re_init()
                _LOGGER.info(
                    "CentralUnit.reconnect: re-connected to central_unit %s",
                    self.instance_name
                )

    def mark_all_devices_availability(self, available: bool) -> None:
        """Mark all device's availability state."""
        for hm_device in self.hm_devices.values():
            hm_device.set_availability(value=available)

    async def get_all_system_variables(self) -> dict[str, Any] | None:
        """Get all system variables from CCU / Homegear."""
        if client := self.get_client():
            return await client.get_all_system_variables()
        return None

    async def get_system_variable(self, name: str) -> Any | None:
        """Get system variable from CCU / Homegear."""
        if client := self.get_client():
            return await client.get_system_variable(name)
        return None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set a system variable on CCU / Homegear."""
        if client := self.get_client():
            await client.set_system_variable(name=name, value=value)

    async def get_service_messages(self) -> list[list[tuple[str, str, Any]]]:
        """Get service messages from CCU / Homegear."""
        service_messages: list[list[tuple[str, str, Any]]] = []
        for client in self._clients.values():
            if client.get_virtual_remote():
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
        device_address: str | None = None,
    ) -> None:
        """Activate or deactivate install-mode on CCU / Homegear."""
        if client := self.get_client_by_interface_id(interface_id=interface_id):
            await client.set_install_mode(
                on=on, t=t, mode=mode, device_address=device_address
            )

    async def get_install_mode(self, interface_id: str) -> int:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        if client := self.get_client_by_interface_id(interface_id=interface_id):
            return int(await client.get_install_mode())
        return 0

    async def set_value(
        self,
        interface_id: str,
        channel_address: str,
        parameter: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set single value on paramset VALUES."""

        if client := self.get_client_by_interface_id(interface_id=interface_id):
            await client.set_value(
                channel_address=channel_address,
                parameter=parameter,
                value=value,
                rx_mode=rx_mode,
            )

    async def put_paramset(
        self,
        interface_id: str,
        channel_address: str,
        paramset: str,
        value: Any,
        rx_mode: str | None = None,
    ) -> None:
        """Set paramsets manually."""

        if client := self.get_client_by_interface_id(interface_id=interface_id):
            await client.put_paramset(
                channel_address=channel_address,
                paramset=paramset,
                value=value,
                rx_mode=rx_mode,
            )

    def _get_virtual_remote(self, device_address: str) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for client in self._clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.device_address == device_address:
                return virtual_remote
        return None

    def get_hm_entity_by_parameter(
        self, channel_address: str, parameter: str
    ) -> GenericEntity | None:
        """Get entity by channel_address and parameter."""
        if ":" in channel_address:
            if device := self.hm_devices.get(get_device_address(channel_address)):
                if entity := device.entities.get((channel_address, parameter)):
                    return entity
        return None

    def has_address(self, address: str) -> bool:
        """Check if address is handled by central_unit."""
        return self.hm_devices.get(get_device_address(address)) is not None

    def get_all_used_parameters(self) -> list[str]:
        """Return used parameters"""
        parameters: set[str] = set()
        for entity in self.hm_entities.values():
            if isinstance(entity, GenericEntity):
                if getattr(entity, "parameter", None):
                    parameters.add(entity.parameter)

        return sorted(parameters)

    def get_used_parameters(self, device_address: str) -> list[str]:
        """Return used parameters"""
        parameters: set[str] = set()
        if device := self.hm_devices.get(device_address):
            for entity in device.entities.values():
                if getattr(entity, "parameter", None):
                    parameters.add(entity.parameter)

        return sorted(parameters)

    async def clear_all(self) -> None:
        """
        Clear all stored data.
        """
        await self.raw_devices.clear()
        await self.paramsets.clear()
        await self.names.clear()
        await self.rooms.clear()


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
        connection_checker_interval = config.CONNECTION_CHECKER_INTERVAL
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
                    await asyncio.sleep(connection_checker_interval)
                    await self._central.reconnect()
                await asyncio.sleep(connection_checker_interval)
            except NoConnection as nex:
                _LOGGER.exception("check_connection: no connection: %s", nex.args)
                await asyncio.sleep(connection_checker_interval)
                continue
            except Exception:
                _LOGGER.exception("check_connection: Exception")


class CentralConfig:
    """Config for a Client."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        xml_rpc_server: xml_rpc.XmlRpcServer,
        domain: str,
        storage_folder: str,
        name: str,
        host: str = LOCALHOST,
        username: str = DEFAULT_USERNAME,
        password: str | None = DEFAULT_PASSWORD,
        tls: bool = DEFAULT_TLS,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        client_session: ClientSession | None = None,
        callback_host: str | None = None,
        callback_port: int | None = None,
        json_port: int | None = None,
    ):
        self.loop = loop
        self.xml_rpc_server = xml_rpc_server
        self.domain = domain
        self.storage_folder = storage_folder
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

    @property
    def device_url(self) -> str:
        """Return the required url."""
        url = "http://"
        if self.tls:
            url = "https://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    def check_config(self) -> bool:
        """Check config."""
        try:
            check_or_create_directory(self.storage_folder)
        except HaHomematicException:
            return False
        return True

    async def get_central(self) -> CentralUnit:
        """Identify the used client."""
        central = CentralUnit(self)
        await central.load_caches()
        return central


class RoomCache:
    """Cache for rooms."""

    def __init__(
        self,
        central: CentralUnit,
    ):
        self._central = central
        self._rooms: dict[str, str] = {}
        self._device_rooms: dict[str, list[str]] = {}

    async def load(self) -> None:
        """Init room cache."""
        self._rooms = await self._get_all_rooms()
        self.identify_device_rooms()

    def identify_device_rooms(self) -> None:
        """
        Identify a possible room of a device.
        A room is relevant for a device, if there is only one room assigned to the channels.
        """
        device_rooms: dict[str, list[str]] = {}
        for address, room in self._rooms.items():
            device_address = get_device_address(address=address)
            if device_address not in device_rooms:
                device_rooms[device_address] = []
            device_rooms[device_address].append(room)
        for device_address, rooms in device_rooms.items():
            if rooms and len(set(rooms)) == 1:
                self._rooms[device_address] = list(set(rooms))[0]

    async def clear(self) -> None:
        """Clear the cache."""
        self._rooms.clear()

    async def _get_all_rooms(self) -> dict[str, str]:
        """Get all rooms, if available."""
        if client := self._central.get_client():
            return await client.get_all_rooms()
        return {}

    def get_room(self, address: str) -> str | None:
        """Return room by address"""
        return self._rooms.get(address)


class BaseCache(ABC):
    """Cache for files."""

    def __init__(
        self,
        central: CentralUnit,
        filename: str,
        cache_dict: dict[str, Any],
    ):
        self._central = central
        self._cache_dir = f"{self._central.central_config.storage_folder}/cache"
        self._filename = f"{self._central.instance_name}_{filename}"
        self._cache_dict = cache_dict

    async def save(self) -> Awaitable[int]:
        """
        Save current name data in NAMES to disk.
        """

        def _save() -> int:
            if not check_or_create_directory(self._cache_dir):
                return DATA_NO_SAVE
            with open(
                file=os.path.join(self._cache_dir, self._filename),
                mode="w",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                json.dump(self._cache_dict, fptr)
            return DATA_SAVE_SUCCESS

        return await self._central.async_add_executor_job(_save)

    async def load(self) -> Awaitable[int]:
        """
        Load file from disk into dict.
        """

        def _load() -> int:
            if not check_or_create_directory(self._cache_dir):
                return DATA_NO_LOAD
            if not os.path.exists(os.path.join(self._cache_dir, self._filename)):
                return DATA_NO_LOAD
            with open(
                file=os.path.join(self._cache_dir, self._filename),
                mode="r",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                self._cache_dict.clear()
                self._cache_dict.update(json.load(fptr))
            return DATA_LOAD_SUCCESS

        return await self._central.async_add_executor_job(_load)

    async def clear(self) -> None:
        """
        Remove stored file from disk.
        """

        def _clear() -> None:
            check_or_create_directory(self._cache_dir)
            if os.path.exists(os.path.join(self._cache_dir, self._filename)):
                os.unlink(os.path.join(self._cache_dir, self._filename))
            self._cache_dict.clear()

        await self._central.async_add_executor_job(_clear)


class RawDevicesCache(BaseCache):
    """Cache for device/channel names."""

    def __init__(self, central: CentralUnit):
        # {interface_id, [device_descriptions]}
        self._devices_raw_cache: dict[str, list[dict[str, Any]]] = {}
        super().__init__(
            central=central,
            filename=FILE_DEVICES,
            cache_dict=self._devices_raw_cache,
        )

        # {interface_id, {device_address, [channel_address]}}
        self._addresses: dict[str, dict[str, list[str]]] = {}
        # {interface_id, {address, device_descriptions}}
        self._dev_descriptions: dict[str, dict[str, dict[str, Any]]] = {}

    def _add_device_descriptions(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """Add device_descriptions to cache."""
        if interface_id not in self._devices_raw_cache:
            self._devices_raw_cache[interface_id] = []
        self._devices_raw_cache[interface_id] = device_descriptions

        self._handle_device_descriptions(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    def add_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """Add device_description to cache."""
        if interface_id not in self._devices_raw_cache:
            self._devices_raw_cache[interface_id] = []

        if device_description not in self._devices_raw_cache[interface_id]:
            self._devices_raw_cache[interface_id].append(device_description)

        self._handle_device_description(
            interface_id=interface_id, device_description=device_description
        )

    def get_device_descriptions(self, interface_id: str) -> list[dict[str, Any]]:
        """Find raw device in cache."""
        return self._devices_raw_cache.get(interface_id, [])

    async def cleanup(self, interface_id: str, deleted_addresses: list[str]) -> None:
        """Remove device from cache."""
        self._add_device_descriptions(
            interface_id=interface_id,
            device_descriptions=[
                device
                for device in self.get_device_descriptions(interface_id)
                if device[ATTR_HM_ADDRESS] not in deleted_addresses
            ],
        )

        for address in deleted_addresses:
            try:
                if ":" not in address and self._addresses.get(interface_id, {}).get(
                    address, []
                ):
                    del self._addresses[interface_id][address]
                if self._dev_descriptions.get(interface_id, {}).get(address, {}):
                    del self._dev_descriptions[interface_id][address]
            except KeyError:
                _LOGGER.exception("Failed to delete: %s", address)
        await self.save()

    def get_addresses(self, interface_id: str) -> dict[str, list[str]]:
        """Return the addresses by interface"""
        return self._addresses.get(interface_id, {})

    def get_channels(self, interface_id: str, device_address: str) -> list[str]:
        """Return the device channels by interface and device_address"""
        return self._addresses.get(interface_id, {}).get(device_address, [])

    def get_interface(self, interface_id: str) -> dict[str, dict[str, Any]]:
        """Return the devices by interface"""
        return self._dev_descriptions.get(interface_id, {})

    def get_device(self, interface_id: str, device_address: str) -> dict[str, Any]:
        """Return the device dict by interface and device_address"""
        return self._dev_descriptions.get(interface_id, {}).get(device_address, {})

    def get_device_with_channels(
        self, interface_id: str, device_address: str
    ) -> dict[str, Any]:
        """Return the device dict by interface and device_address"""
        data: dict[str, Any] = {
            device_address: self._dev_descriptions.get(interface_id, {}).get(
                device_address, {}
            )
        }
        children = data[device_address]["CHILDREN"]
        for channel_address in children:
            data[channel_address] = self._dev_descriptions.get(interface_id, {}).get(
                channel_address, {}
            )
        return data

    def get_device_parameter(
        self, interface_id: str, device_address: str, parameter: str
    ) -> Any | None:
        """Return the device parameter by interface and device_address"""
        return (
            self._dev_descriptions.get(interface_id, {})
            .get(device_address, {})
            .get(parameter)
        )

    def _handle_device_descriptions(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """
        Handle provided list of device descriptions.
        """
        for device_description in device_descriptions:
            self._handle_device_description(
                interface_id=interface_id, device_description=device_description
            )

    def _handle_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """
        Handle provided list of device descriptions.
        """
        if interface_id not in self._addresses:
            self._addresses[interface_id] = {}
        if interface_id not in self._dev_descriptions:
            self._dev_descriptions[interface_id] = {}

        address = device_description[ATTR_HM_ADDRESS]
        self._dev_descriptions[interface_id][address] = device_description
        if ":" not in address and address not in self._addresses[interface_id]:
            self._addresses[interface_id][address] = []
        if ":" in address:
            device_address = get_device_address(address)
            self._addresses[interface_id][device_address].append(address)

    async def load(self) -> Awaitable[int]:
        """
        Load device data from disk into devices_raw.
        """
        result = await super().load()
        for interface_id, device_descriptions in self._devices_raw_cache.items():
            self._handle_device_descriptions(interface_id, device_descriptions)
        return result


class NamesCache(BaseCache):
    """Cache for device/channel names."""

    def __init__(self, central: CentralUnit):
        # {address, name}
        self._names_cache: dict[str, str] = {}
        super().__init__(
            central=central,
            filename=FILE_NAMES,
            cache_dict=self._names_cache,
        )

    def add(self, address: str, name: str) -> None:
        """Add name to cache."""
        if address not in self._names_cache:
            self._names_cache[address] = name

    def get_name(self, address: str) -> str | None:
        """Get name from cache."""
        return self._names_cache.get(address)

    def remove(self, address: str) -> None:
        """Remove name from cache."""
        if address in self._names_cache:
            del self._names_cache[address]


class ParamsetCache(BaseCache):
    """Cache for paramsets."""

    def __init__(self, central: CentralUnit):
        # {interface_id, {channel_address, paramsets}}
        self._paramsets_cache: dict[str, dict[str, dict[str, dict[str, Any]]]] = {}
        super().__init__(
            central=central,
            filename=FILE_PARAMSETS,
            cache_dict=self._paramsets_cache,
        )

        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: dict[tuple[str, str], list[int]] = {}

    def add(
        self,
        interface_id: str,
        channel_address: str,
        paramset: str,
        paramset_description: dict[str, Any],
    ) -> None:
        """Add paramset description to cache."""
        if interface_id not in self._paramsets_cache:
            self._paramsets_cache[interface_id] = {}
        if channel_address not in self._paramsets_cache[interface_id]:
            self._paramsets_cache[interface_id][channel_address] = {}
        if paramset not in self._paramsets_cache[interface_id][channel_address]:
            self._paramsets_cache[interface_id][channel_address][paramset] = {}

        self._paramsets_cache[interface_id][channel_address][
            paramset
        ] = paramset_description

    def remove(self, interface_id: str, channel_address: str) -> None:
        """Remove paramset from cache."""
        if interface := self._paramsets_cache.get(interface_id):
            if channel_address in interface:
                del self._paramsets_cache[interface_id][channel_address]

    def get_by_interface(
        self, interface_id: str
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """Get paramset descriptions by interface from cache."""
        return self._paramsets_cache.get(interface_id, {})

    def get_by_interface_channel_address(
        self, interface_id: str, channel_address: str
    ) -> dict[str, dict[str, Any]]:
        """Get paramset descriptions from cache by interface, channel_address."""
        return self._paramsets_cache.get(interface_id, {}).get(channel_address, {})

    def get_by_interface_channel_address_paramset(
        self, interface_id: str, channel_address: str, paramset: str
    ) -> dict[str, Any]:
        """Get paramset description by interface, channel_address, paramset in cache."""
        return (
            self._paramsets_cache.get(interface_id, {})
            .get(channel_address, {})
            .get(paramset, {})
        )

    def has_multiple_channels(self, channel_address: str, parameter: str) -> bool:
        """Check if parameter is in multiple channels per device."""
        if ":" not in channel_address:
            return False
        if channels := self._address_parameter_cache.get(
            (get_device_address(channel_address), parameter)
        ):
            return len(set(channels)) > 1
        return False

    def get_all_parameters(self) -> list[str]:
        """Return all parameters"""
        parameters: set[str] = set()
        for channel in self._paramsets_cache.values():
            for channel_address in channel:
                for paramset in channel[channel_address].values():
                    parameters.update(paramset)

        return sorted(parameters)

    def get_parameters(self, device_address: str) -> list[str]:
        """Return all parameters of a device"""
        parameters: set[str] = set()
        for channel in self._paramsets_cache.values():
            for channel_address in channel:
                if channel_address.startswith(device_address):
                    for paramset in channel[channel_address].values():
                        parameters.update(paramset)

        return sorted(parameters)

    def _init_address_parameter_list(self) -> None:
        """Initialize an device_address/parameter list to identify if a parameter name exists is in multiple channels."""
        for channel_paramsets in self._paramsets_cache.values():
            for channel_address, paramsets in channel_paramsets.items():
                if ":" not in channel_address:
                    continue
                device_address = get_device_address(channel_address)

                for paramset in paramsets.values():
                    for parameter in paramset:
                        if (
                            device_address,
                            parameter,
                        ) not in self._address_parameter_cache:
                            self._address_parameter_cache[
                                (device_address, parameter)
                            ] = []
                        self._address_parameter_cache[
                            (device_address, parameter)
                        ].append(get_device_channel(channel_address))

    async def load(self) -> Awaitable[int]:
        """
        Load paramset data from disk into paramsets.
        """
        result = await super().load()
        self._init_address_parameter_list()
        return result

    async def save(self) -> Awaitable[int]:
        """
        Save current paramset data to disk.
        """
        result = await super().save()
        self._init_address_parameter_list()
        return result


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
