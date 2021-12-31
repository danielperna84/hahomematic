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
    HA_DOMAIN,
    HM_VIRTUAL_REMOTE_HM,
    HM_VIRTUAL_REMOTE_HMIP,
    LOCALHOST,
    MANUFACTURER,
    HmPlatform,
)
import hahomematic.data as hm_data
from hahomematic.device import HmDevice, create_devices
from hahomematic.entity import BaseEntity, GenericEntity
import hahomematic.helpers
from hahomematic.helpers import (
    check_or_create_directory,
    get_device_address,
    get_device_channel,
)
from hahomematic.hub import HmDummyHub, HmHub
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.xml_rpc_proxy import NoConnection
import hahomematic.xml_rpc_server as xml_rpc

_LOGGER = logging.getLogger(__name__)


class CentralUnit:
    """Central unit that collects everything required to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig):
        _LOGGER.debug("CentralUnit.__init__")
        self.central_config: CentralConfig = central_config

        self.instance_name: str = self.central_config.name
        self._available: bool = True
        self._loop: asyncio.AbstractEventLoop = self.central_config.loop
        self._xml_rpc_server: xml_rpc.XmlRpcServer = self.central_config.xml_rpc_server
        self._xml_rpc_server.register_central(self)
        self.option_enable_virtual_channels: bool = (
            self.central_config.option_enable_virtual_channels
        )
        self._model: str | None = None

        # Caches for CCU data
        self.paramsets: ParamsetCache = ParamsetCache(central=self)
        self.names: NamesCache = NamesCache(central=self)
        self.raw_devices: RawDevicesCache = RawDevicesCache(central=self)

        # {interface_id, client}
        self.clients: dict[str, hm_client.Client] = {}
        # {url, client}
        self.clients_by_init_url: dict[str, list[hm_client.Client]] = {}

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

    def create_hub(self) -> HmHub | HmDummyHub:
        """Create the hub."""
        hub: HmHub | HmDummyHub
        if self.model is BACKEND_PYDEVCCU:
            hub = HmDummyHub(central=self)
        else:
            hub = HmHub(
                central=self,
                use_entities=self.central_config.option_enable_sensors_for_system_variables,
            )
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
            "identifiers": {(HA_DOMAIN, self.instance_name)},
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

    async def load_caches(self) -> None:
        """Load files to caches."""
        try:
            await self.raw_devices.load()
            await self.paramsets.load()
            await self.names.load()
        except json.decoder.JSONDecodeError:
            _LOGGER.warning("Failed to load caches.")
            await self.clear_all()

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
        self.stop_connection_checker()
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
        self._xml_rpc_server.un_register_central(central=self)
        # un-register and stop XMLRPCServer, if possible
        xml_rpc.un_register_xml_rpc_server()

        _LOGGER.debug("CentralUnit.stop: Removing instance")
        del hm_data.INSTANCES[self.instance_name]

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

    def stop_connection_checker(self) -> None:
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
                    self.mark_all_devices_availability(available=False)
                    self._available = False
                return False
        if not self._available:
            self.mark_all_devices_availability(available=True)
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
        for client in self.clients.values():
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
        if client := self.get_client(interface_id=interface_id):
            await client.set_install_mode(
                on=on, t=t, mode=mode, device_address=device_address
            )

    async def get_install_mode(self, interface_id: str) -> int:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        if client := self.get_client(interface_id=interface_id):
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

        if client := self.get_client(interface_id=interface_id):
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

        if client := self.get_client(interface_id=interface_id):
            await client.put_paramset(
                channel_address=channel_address,
                paramset=paramset,
                value=value,
                rx_mode=rx_mode,
            )

    def _get_virtual_remote(self, device_address: str) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for client in self.clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.device_address == device_address:
                return virtual_remote
        return None

    async def press_virtual_remote_key(
        self, channel_address: str, parameter: str
    ) -> None:
        """Simulate a key press on the virtual remote."""
        if ":" not in channel_address:
            _LOGGER.warning(
                "CentralUnit.press_virtual_remote_key: channel_address is missing channel information."
            )

        if channel_address.startswith(HM_VIRTUAL_REMOTE_HM.upper()):
            channel_address = channel_address.replace(
                HM_VIRTUAL_REMOTE_HM.upper(), HM_VIRTUAL_REMOTE_HM
            )
        if channel_address.startswith(HM_VIRTUAL_REMOTE_HMIP.upper()):
            channel_address = channel_address.replace(
                HM_VIRTUAL_REMOTE_HMIP.upper(), HM_VIRTUAL_REMOTE_HMIP
            )

        if virtual_remote := self._get_virtual_remote(
            get_device_address(channel_address)
        ):
            if virtual_remote_channel := virtual_remote.action_events.get(
                (channel_address, parameter)
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

    def get_client(self, interface_id: str | None = None) -> hm_client.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        if interface_id:
            try:
                return self.clients[interface_id]
            except IndexError as err:
                message = (
                    f"Can't resolve interface for {self.instance_name}: {interface_id}"
                )
                _LOGGER.warning(message)
                raise hahomematic.helpers.ClientException(message) from err
        else:
            client: hm_client.Client | None = None
            for client in self.clients.values():
                if client.get_virtual_remote():
                    return client
            return client

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


class CentralConfig:
    """Config for a Client."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        xml_rpc_server: xml_rpc.XmlRpcServer,
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
        json_tls: bool = DEFAULT_TLS,
        option_enable_virtual_channels: bool = False,
        option_enable_sensors_for_system_variables: bool = False,
    ):
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
        self.option_enable_virtual_channels = option_enable_virtual_channels
        self.option_enable_sensors_for_system_variables = (
            option_enable_sensors_for_system_variables
        )

    @property
    def device_url(self) -> str:
        """Return the required url."""
        url = "http://"
        if self.json_tls:
            url = "https://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    async def get_central(self) -> CentralUnit:
        """Identify the used client."""
        central = CentralUnit(self)
        await central.load_caches()
        return central


class BaseCache(ABC):
    """Cache for files."""

    def __init__(
        self,
        central: CentralUnit,
        filename: str,
        cache_dict: dict[str, Any],
    ):
        self._central = central
        self._cache_dir = config.CACHE_DIR
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
