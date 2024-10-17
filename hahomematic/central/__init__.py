"""
CentralUnit module.

This is the python representation of a CCU.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine, Mapping, Set as AbstractSet
from datetime import datetime
from functools import partial
import logging
from logging import DEBUG
import threading
from time import sleep
from typing import Any, Final, cast

from aiohttp import ClientSession
import orjson
import voluptuous as vol

from hahomematic import client as hmcl, config
from hahomematic.async_support import Looper, loop_check
from hahomematic.caches.dynamic import CentralDataCache, DeviceDetailsCache
from hahomematic.caches.persistent import DeviceDescriptionCache, ParamsetDescriptionCache
from hahomematic.caches.visibility import ParameterVisibilityCache
from hahomematic.central import xml_rpc_server as xmlrpc
from hahomematic.central.decorators import callback_backend_system, callback_event
from hahomematic.client.json_rpc import JsonRpcAioHttpClient
from hahomematic.client.xml_rpc import XmlRpcProxy
from hahomematic.const import (
    CALLBACK_TYPE,
    DATETIME_FORMAT_MILLIS,
    DEFAULT_INCLUDE_INTERNAL_PROGRAMS,
    DEFAULT_INCLUDE_INTERNAL_SYSVARS,
    DEFAULT_MAX_READ_WORKERS,
    DEFAULT_PROGRAM_SCAN_ENABLED,
    DEFAULT_SYSVAR_SCAN_ENABLED,
    DEFAULT_TLS,
    DEFAULT_VERIFY_TLS,
    ENTITY_EVENTS,
    ENTITY_KEY,
    EVENT_AVAILABLE,
    EVENT_DATA,
    EVENT_INTERFACE_ID,
    EVENT_TYPE,
    IGNORE_FOR_UN_IGNORE_PARAMETERS,
    IP_ANY_V4,
    PLATFORMS,
    PORT_ANY,
    UN_IGNORE_WILDCARD,
    BackendSystemEvent,
    DeviceDescription,
    DeviceFirmwareState,
    HmPlatform,
    HomematicEventType,
    InterfaceEventType,
    InterfaceName,
    Operations,
    Parameter,
    ParamsetKey,
    ProxyInitState,
    SystemInformation,
)
from hahomematic.exceptions import (
    BaseHomematicException,
    HaHomematicConfigException,
    HaHomematicException,
    NoClients,
    NoConnection,
)
from hahomematic.performance import measure_execution_time
from hahomematic.platforms import create_entities_and_events
from hahomematic.platforms.custom import CustomEntity, create_custom_entities
from hahomematic.platforms.decorators import info_property, service
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.entity import BaseParameterEntity, CallbackEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic import GenericEntity
from hahomematic.platforms.hub import GenericHubEntity, GenericSystemVariable, HmProgramButton, Hub
from hahomematic.platforms.support import PayloadMixin
from hahomematic.support import (
    check_config,
    get_channel_no,
    get_device_address,
    get_entity_key,
    get_ip_addr,
    reduce_args,
)

__all__ = ["CentralConfig", "CentralUnit", "INTERFACE_EVENT_SCHEMA"]

_LOGGER: Final = logging.getLogger(__name__)

# {instance_name, central}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}
ConnectionProblemIssuer = JsonRpcAioHttpClient | XmlRpcProxy

INTERFACE_EVENT_SCHEMA = vol.Schema(
    {
        vol.Required(EVENT_INTERFACE_ID): str,
        vol.Required(EVENT_TYPE): InterfaceEventType,
        vol.Required(EVENT_DATA): vol.Schema(
            {vol.Required(vol.Any(str)): vol.Schema(vol.Any(str, int, bool))}
        ),
    }
)


class CentralUnit(PayloadMixin):
    """Central unit that collects everything to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._started: bool = False
        self._sema_add_devices: Final = asyncio.Semaphore()
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        # Keep the config for the central
        self._config: Final = central_config
        self._model: str | None = None
        self._looper = Looper()
        self._xml_rpc_server: xmlrpc.XmlRpcServer | None = None
        self._json_rpc_client: Final = central_config.json_rpc_client

        # Caches for CCU data
        self._data_cache: Final = CentralDataCache(central=self)
        self._device_details: Final = DeviceDetailsCache(central=self)
        self._device_descriptions: Final = DeviceDescriptionCache(central=self)
        self._paramset_descriptions: Final = ParamsetDescriptionCache(central=self)
        self._parameter_visibility: Final = ParameterVisibilityCache(central=self)

        self._primary_client: hmcl.Client | None = None
        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        self._entity_event_subscriptions: Final[
            dict[ENTITY_KEY, list[Callable[[Any], Coroutine[Any, Any, None]]]]
        ] = {}
        # {device_address, device}
        self._devices: Final[dict[str, HmDevice]] = {}
        # {sysvar_name, sysvar_entity}
        self._sysvar_entities: Final[dict[str, GenericSystemVariable]] = {}
        # {sysvar_name, program_button}U
        self._program_buttons: Final[dict[str, HmProgramButton]] = {}
        # Signature: (name, *args)
        # e.g. DEVICES_CREATED, HUB_REFRESHED
        self._backend_system_callbacks: Final[set[Callable]] = set()
        # Signature: (interface_id, channel_address, parameter, value)
        # Re-Fired events from CCU for parameter updates
        self._backend_parameter_callbacks: Final[set[Callable]] = set()
        # Signature: (event_type, event_data)
        # Events like INTERFACE, KEYPRESS, ...
        self._homematic_callbacks: Final[set[Callable]] = set()

        CENTRAL_INSTANCES[self.name] = self
        self._connection_checker: Final = _ConnectionChecker(central=self)
        self._hub: Hub = Hub(central=self)
        self._version: str | None = None
        # store last event received datetime by interface
        self.last_events: Final[dict[str, datetime]] = {}
        self._callback_ip_addr: str = IP_ANY_V4
        self._listen_ip_addr: str = IP_ANY_V4
        self._listen_port: int = PORT_ANY

    @property
    def available(self) -> bool:
        """Return the availability of the central."""
        return all(client.available for client in self._clients.values())

    @property
    def callback_ip_addr(self) -> str:
        """Return the xml rpc server callback ip address."""
        return self._callback_ip_addr

    @info_property
    def central_url(self) -> str:
        """Return the central_orl from config."""
        return self._config.central_url

    @property
    def clients(self) -> tuple[hmcl.Client, ...]:
        """Return all clients."""
        return tuple(self._clients.values())

    @property
    def config(self) -> CentralConfig:
        """Return central config."""
        return self._config

    @property
    def data_cache(self) -> CentralDataCache:
        """Return data_cache cache."""
        return self._data_cache

    @property
    def device_details(self) -> DeviceDetailsCache:
        """Return device_details cache."""
        return self._device_details

    @property
    def device_descriptions(self) -> DeviceDescriptionCache:
        """Return device_descriptions cache."""
        return self._device_descriptions

    @property
    def devices(self) -> tuple[HmDevice, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        if self._connection_checker.is_alive():
            return True
        return bool(
            self._xml_rpc_server
            and self._xml_rpc_server.no_central_assigned
            and self._xml_rpc_server.is_alive()
        )

    @property
    def interface_ids(self) -> tuple[str, ...]:
        """Return all associated interface ids."""
        return tuple(self._clients)

    @property
    def interfaces(self) -> tuple[str, ...]:
        """Return all associated interfaces."""
        return tuple(client.interface for client in self._clients.values())

    @property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return all(client.is_callback_alive() for client in self._clients.values())

    @property
    def paramset_descriptions(self) -> ParamsetDescriptionCache:
        """Return paramset_descriptions cache."""
        return self._paramset_descriptions

    @property
    def parameter_visibility(self) -> ParameterVisibilityCache:
        """Return parameter_visibility cache."""
        return self._parameter_visibility

    @property
    def primary_client(self) -> hmcl.Client | None:
        """Return the primary client of the backend."""
        if self._primary_client is not None:
            return self._primary_client
        if client := self._get_primary_client():
            self._primary_client = client
        return self._primary_client

    @property
    def listen_ip_addr(self) -> str:
        """Return the xml rpc server listening ip address."""
        return self._listen_ip_addr

    @property
    def listen_port(self) -> int:
        """Return the xml rpc listening server port."""
        return self._listen_port

    @property
    def looper(self) -> Looper:
        """Return the loop support."""
        return self._looper

    @info_property
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model and (client := self.primary_client):
            self._model = client.model
        return self._model

    @info_property
    def name(self) -> str:
        """Return the name of the backend."""
        return self._config.name

    @property
    def path(self) -> str:
        """Return the base path of the entity."""
        return f"{self._config.base_path}{self.name}"

    @property
    def program_buttons(self) -> tuple[HmProgramButton, ...]:
        """Return the program entities."""
        return tuple(self._program_buttons.values())

    @property
    def started(self) -> bool:
        """Return if the central is started."""
        return self._started

    @property
    def supports_ping_pong(self) -> bool:
        """Return the backend supports ping pong."""
        if primary_client := self.primary_client:
            return primary_client.supports_ping_pong
        return False

    @property
    def system_information(self) -> SystemInformation:
        """Return the system_information of the backend."""
        if client := self.primary_client:
            return client.system_information
        return SystemInformation()

    @property
    def sysvar_entities(self) -> tuple[GenericSystemVariable, ...]:
        """Return the sysvar entities."""
        return tuple(self._sysvar_entities.values())

    @info_property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if self._version is None:
            versions = [client.version for client in self._clients.values() if client.version]
            self._version = max(versions) if versions else None
        return self._version

    def add_sysvar_entity(self, sysvar_entity: GenericSystemVariable) -> None:
        """Add new program button."""
        if (ccu_var_name := sysvar_entity.ccu_var_name) is not None:
            self._sysvar_entities[ccu_var_name] = sysvar_entity

    def remove_sysvar_entity(self, name: str) -> None:
        """Remove a sysvar entity."""
        if (sysvar_entity := self.get_sysvar_entity(name=name)) is not None:
            sysvar_entity.fire_device_removed_callback()
            del self._sysvar_entities[name]

    def add_program_button(self, program_button: HmProgramButton) -> None:
        """Add new program button."""
        self._program_buttons[program_button.pid] = program_button

    def remove_program_button(self, pid: str) -> None:
        """Remove a program button."""
        if (program_button := self.get_program_button(pid=pid)) is not None:
            program_button.fire_device_removed_callback()
            del self._program_buttons[pid]

    async def save_caches(
        self, save_device_descriptions: bool = False, save_paramset_descriptions: bool = False
    ) -> None:
        """Save persistent caches."""
        if save_device_descriptions:
            await self._device_descriptions.save()
        if save_paramset_descriptions:
            await self._paramset_descriptions.save()

    async def start(self) -> None:
        """Start processing of the central unit."""

        if self._started:
            _LOGGER.debug("START: Central %s already started", self.name)
            return
        if self._config.interface_configs and (
            ip_addr := await self._identify_ip_addr(
                port=tuple(self._config.interface_configs)[0].port
            )
        ):
            self._callback_ip_addr = ip_addr
            self._listen_ip_addr = (
                self._config.listen_ip_addr if self._config.listen_ip_addr else ip_addr
            )

        listen_port: int = (
            self._config.listen_port
            if self._config.listen_port
            else self._config.callback_port or self._config.default_callback_port
        )
        try:
            if (
                xml_rpc_server := xmlrpc.create_xml_rpc_server(
                    ip_addr=self._listen_ip_addr, port=listen_port
                )
                if self._config.enable_server
                else None
            ):
                self._xml_rpc_server = xml_rpc_server
                self._listen_port = xml_rpc_server.listen_port
                self._xml_rpc_server.add_central(self)
        except OSError as oserr:
            raise HaHomematicException(
                f"START: Failed to start central unit {self.name}: {reduce_args(args=oserr.args)}"
            ) from oserr

        await self._parameter_visibility.load()
        if self._config.start_direct:
            if await self._create_clients():
                for client in self._clients.values():
                    await self._refresh_device_descriptions(client=client)
        else:
            await self._start_clients()
            if self._config.enable_server:
                self._start_connection_checker()

        self._started = True

    async def stop(self) -> None:
        """Stop processing of the central unit."""
        if not self._started:
            _LOGGER.debug("STOP: Central %s not started", self.name)
            return
        await self.save_caches(save_device_descriptions=True, save_paramset_descriptions=True)
        self._stop_connection_checker()
        await self._stop_clients()
        if self._json_rpc_client.is_activated:
            await self._json_rpc_client.logout()

        if self._xml_rpc_server:
            # un-register this instance from XmlRPC-Server
            self._xml_rpc_server.remove_central(central=self)
            # un-register and stop XmlRPC-Server, if possible
            if self._xml_rpc_server.no_central_assigned:
                self._xml_rpc_server.stop()
            _LOGGER.debug("STOP: XmlRPC-Server stopped")
        else:
            _LOGGER.debug(
                "STOP: shared XmlRPC-Server NOT stopped. "
                "There is still another central instance registered"
            )

        _LOGGER.debug("STOP: Removing instance")
        if self.name in CENTRAL_INSTANCES:
            del CENTRAL_INSTANCES[self.name]

        # wait until tasks are finished
        await self.looper.block_till_done()

        while self._has_active_threads:  # noqa: ASYNC110
            await asyncio.sleep(1)
        self._started = False

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._stop_clients()
        await self._start_clients()

    async def refresh_firmware_data(self, device_address: str | None = None) -> None:
        """Refresh device firmware data."""
        if (
            device_address
            and (device := self.get_device(address=device_address)) is not None
            and device.is_updatable
        ):
            await self._refresh_device_descriptions(
                client=device.client, device_address=device_address
            )
            device.refresh_firmware_data()
        else:
            for client in self._clients.values():
                await self._refresh_device_descriptions(client=client)
            for device in self._devices.values():
                if device.is_updatable:
                    device.refresh_firmware_data()

    async def refresh_firmware_data_by_state(
        self, device_firmware_states: tuple[DeviceFirmwareState, ...]
    ) -> None:
        """Refresh device firmware data for processing devices."""
        for device in [
            device_in_state
            for device_in_state in self._devices.values()
            if device_in_state.firmware_update_state in device_firmware_states
        ]:
            await self.refresh_firmware_data(device_address=device.address)

    async def _refresh_device_descriptions(
        self, client: hmcl.Client, device_address: str | None = None
    ) -> None:
        """Refresh device descriptions."""
        if (
            device_descriptions := await client.get_device_description(
                device_address=device_address
            )
            if device_address
            else await client.get_all_device_descriptions()
        ):
            await self._add_new_devices(
                interface_id=client.interface_id,
                device_descriptions=device_descriptions,
            )

    async def _start_clients(self) -> None:
        """Start clients ."""
        if await self._create_clients():
            await self._load_caches()
            if new_device_addresses := self._check_for_new_device_addresses():
                await self._create_devices(new_device_addresses=new_device_addresses)
            await self._init_hub()
            await self._init_clients()

    async def _stop_clients(self) -> None:
        """Stop clients."""
        await self._de_init_clients()
        for client in self._clients.values():
            _LOGGER.debug("STOP_CLIENTS: Stopping %s", client.interface_id)
            await client.stop()
        _LOGGER.debug("STOP_CLIENTS: Clearing existing clients.")
        self._clients.clear()

    async def _create_clients(self) -> bool:
        """Create clients for the central unit. Start connection checker afterwards."""
        if len(self._clients) > 0:
            _LOGGER.warning(
                "CREATE_CLIENTS: Clients for %s are already created",
                self.name,
            )
            return False
        if len(self._config.interface_configs) == 0:
            _LOGGER.warning(
                "CREATE_CLIENTS failed: No Interfaces for %s defined",
                self.name,
            )
            return False

        for interface_config in self._config.interface_configs:
            try:
                if client := await hmcl.create_client(
                    central=self,
                    interface_config=interface_config,
                ):
                    if (
                        available_interfaces := client.system_information.available_interfaces
                    ) and (interface_config.interface not in available_interfaces):
                        _LOGGER.debug(
                            "CREATE_CLIENTS failed: Interface: %s is not available for backend",
                            interface_config.interface,
                        )
                        continue
                    _LOGGER.debug(
                        "CREATE_CLIENTS: Adding client %s to %s",
                        client.interface_id,
                        self.name,
                    )
                    self._clients[client.interface_id] = client
            except BaseHomematicException as ex:
                self.fire_interface_event(
                    interface_id=interface_config.interface_id,
                    interface_event_type=InterfaceEventType.PROXY,
                    data={EVENT_AVAILABLE: False},
                )
                _LOGGER.warning(
                    "CREATE_CLIENTS failed: No connection to interface %s [%s]",
                    interface_config.interface_id,
                    reduce_args(args=ex.args),
                )

        if self.has_clients:
            _LOGGER.debug(
                "CREATE_CLIENTS: All clients successfully created for %s",
                self.name,
            )
            return True

        _LOGGER.debug("CREATE_CLIENTS failed for %s", self.name)
        return False

    async def _init_clients(self) -> None:
        """Init clients of control unit, and start connection checker."""
        for client in self._clients.values():
            if await client.proxy_init() == ProxyInitState.INIT_SUCCESS:
                _LOGGER.debug("INIT_CLIENTS: client for %s initialized", client.interface_id)

    async def _de_init_clients(self) -> None:
        """De-init clients."""
        for name, client in self._clients.items():
            if await client.proxy_de_init():
                _LOGGER.debug("DE_INIT_CLIENTS: Proxy de-initialized: %s", name)

    async def _init_hub(self) -> None:
        """Init the hub."""
        await self._hub.fetch_program_data(scheduled=True)
        await self._hub.fetch_sysvar_data(scheduled=True)

    @loop_check
    def fire_interface_event(
        self,
        interface_id: str,
        interface_event_type: InterfaceEventType,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Fire an event about the interface status."""
        data = data or {}
        event_data: dict[str, Any] = {
            EVENT_INTERFACE_ID: interface_id,
            EVENT_TYPE: interface_event_type,
            EVENT_DATA: data,
        }

        self.fire_homematic_callback(
            event_type=HomematicEventType.INTERFACE,
            event_data=cast(dict[str, Any], INTERFACE_EVENT_SCHEMA(event_data)),
        )

    async def _identify_ip_addr(self, port: int) -> str:
        """Identify IP used for callbacks, xmlrpc_server."""

        ip_addr: str | None = None
        while ip_addr is None:
            try:
                ip_addr = await self.looper.async_add_executor_job(
                    get_ip_addr, self._config.host, port, name="get_ip_addr"
                )
            except HaHomematicException:
                ip_addr = "127.0.0.1"
            if ip_addr is None:
                _LOGGER.warning(
                    "GET_IP_ADDR: Waiting for %i s,", config.CONNECTION_CHECKER_INTERVAL
                )
                await asyncio.sleep(config.CONNECTION_CHECKER_INTERVAL)
        return ip_addr

    def _start_connection_checker(self) -> None:
        """Start the connection checker."""
        _LOGGER.debug(
            "START_CONNECTION_CHECKER: Starting connection_checker for %s",
            self.name,
        )
        self._connection_checker.start()

    def _stop_connection_checker(self) -> None:
        """Start the connection checker."""
        self._connection_checker.stop()
        _LOGGER.debug(
            "STOP_CONNECTION_CHECKER: Stopped connection_checker for %s",
            self.name,
        )

    async def validate_config_and_get_system_information(self) -> SystemInformation:
        """Validate the central configuration."""
        if len(self._config.interface_configs) == 0:
            raise NoClients("validate_config: No clients defined.")

        system_information = SystemInformation()
        for interface_config in self._config.interface_configs:
            client = await hmcl.create_client(central=self, interface_config=interface_config)
            if not system_information.serial:
                system_information = client.system_information
        return system_information

    def get_client(self, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id."""
        if not self.has_client(interface_id=interface_id):
            raise HaHomematicException(
                f"get_client: interface_id {interface_id} does not exist on {self.name}"
            )
        return self._clients[interface_id]

    def get_device(self, address: str) -> HmDevice | None:
        """Return homematic device."""
        d_address = get_device_address(address=address)
        return self._devices.get(d_address)

    def get_entity_by_custom_id(self, custom_id: str) -> CallbackEntity | None:
        """Return homematic entity by custom_id."""
        for entity in self.get_entities(registered=True):
            if entity.custom_id == custom_id:
                return entity
        return None

    def get_entities(
        self,
        platform: HmPlatform | None = None,
        exclude_no_create: bool = True,
        registered: bool | None = None,
    ) -> tuple[CallbackEntity, ...]:
        """Return all externally registered entities."""
        all_entities: list[CallbackEntity] = []
        for device in self._devices.values():
            all_entities.extend(
                device.get_entities(
                    platform=platform, exclude_no_create=exclude_no_create, registered=registered
                )
            )
        return tuple(all_entities)

    def get_readable_generic_entities(
        self, paramset_key: ParamsetKey | None = None
    ) -> tuple[GenericEntity, ...]:
        """Return the readable generic entities."""
        return tuple(
            ge
            for ge in self.get_entities()
            if (
                isinstance(ge, GenericEntity)
                and ge.is_readable
                and ((paramset_key and ge.paramset_key == paramset_key) or paramset_key is None)
            )
        )

    def _get_primary_client(self) -> hmcl.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        client: hmcl.Client | None = None
        for client in self._clients.values():
            if (
                client.interface in (InterfaceName.HMIP_RF, InterfaceName.BIDCOS_RF)
                and client.available
            ):
                return client
        return client

    def get_hub_entities(
        self, platform: HmPlatform | None = None, registered: bool | None = None
    ) -> tuple[GenericHubEntity, ...]:
        """Return the hub entities."""
        return tuple(
            he
            for he in (self.program_buttons + self.sysvar_entities)
            if (platform is None or he.platform == platform)
            and (registered is None or he.is_registered == registered)
        )

    def get_events(
        self, event_type: HomematicEventType, registered: bool | None = None
    ) -> tuple[tuple[GenericEvent, ...], ...]:
        """Return all channel event entities."""
        hm_channel_events: list[tuple[GenericEvent, ...]] = []
        for device in self.devices:
            for channel_events in device.get_events(event_type=event_type).values():
                if registered is None or (channel_events[0].is_registered == registered):
                    hm_channel_events.append(channel_events)
                    continue
        return tuple(hm_channel_events)

    def get_virtual_remotes(self) -> tuple[HmDevice, ...]:
        """Get the virtual remote for the Client."""
        return tuple(
            cl.get_virtual_remote()  # type: ignore[misc]
            for cl in self._clients.values()
            if cl.get_virtual_remote() is not None
        )

    def has_client(self, interface_id: str) -> bool:
        """Check if client exists in central."""
        return interface_id in self._clients

    @property
    def has_clients(self) -> bool:
        """Check if all configured clients exists in central."""
        count_client = len(self._clients)
        count_client_defined = len(self._config.interface_configs)
        return count_client > 0 and count_client == count_client_defined

    async def _load_caches(self) -> None:
        """Load files to caches."""
        try:
            await self._device_descriptions.load()
            await self._paramset_descriptions.load()
            await self._device_details.load()
            await self._data_cache.load()
        except orjson.JSONDecodeError:  # pragma: no cover
            _LOGGER.warning("LOAD_CACHES failed: Unable to load caches for %s", self.name)
            await self.clear_caches()

    async def _create_devices(self, new_device_addresses: dict[str, set[str]]) -> None:
        """Trigger creation of the objects that expose the functionality."""
        if not self._clients:
            raise HaHomematicException(
                f"CREATE_DEVICES failed: No clients initialized. Not starting central {self.name}."
            )
        _LOGGER.debug("CREATE_DEVICES: Starting to create devices for %s", self.name)

        new_devices = set[HmDevice]()

        for interface_id, device_addresses in new_device_addresses.items():
            for device_address in device_addresses:
                # Do we check for duplicates here? For now, we do.
                if device_address in self._devices:
                    continue
                device: HmDevice | None = None
                try:
                    device = HmDevice(
                        central=self,
                        interface_id=interface_id,
                        device_address=device_address,
                    )
                except Exception as ex:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create device: %s, %s",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                        interface_id,
                        device_address,
                    )
                try:
                    if device:
                        create_entities_and_events(device=device)
                        create_custom_entities(device=device)
                        await device.load_value_cache()
                        new_devices.add(device)
                        self._devices[device_address] = device
                except Exception as ex:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create entities: %s, %s",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self.name)

        if new_devices:
            new_entities = _get_new_entities(new_devices=new_devices)
            new_channel_events = _get_new_channel_events(new_devices=new_devices)
            self.fire_backend_system_callback(
                system_event=BackendSystemEvent.DEVICES_CREATED,
                new_entities=new_entities,
                new_channel_events=new_channel_events,
            )

    async def delete_device(self, interface_id: str, device_address: str) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICE: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if (device := self._devices.get(device_address)) is None:
            return

        await self.delete_devices(
            interface_id=interface_id, addresses=[device_address, *list(device.channels.keys())]
        )

    @callback_backend_system(system_event=BackendSystemEvent.DELETE_DEVICES)
    async def delete_devices(self, interface_id: str, addresses: tuple[str, ...]) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        for address in addresses:
            if device := self._devices.get(address):
                self.remove_device(device=device)
        await self.save_caches()

    @callback_backend_system(system_event=BackendSystemEvent.NEW_DEVICES)
    async def add_new_devices(
        self, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]
    ) -> None:
        """Add new devices to central unit."""
        await self._add_new_devices(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    @measure_execution_time
    async def _add_new_devices(
        self, interface_id: str, device_descriptions: tuple[DeviceDescription, ...]
    ) -> None:
        """Add new devices to central unit."""
        _LOGGER.debug(
            "ADD_NEW_DEVICES: interface_id = %s, device_descriptions = %s",
            interface_id,
            len(device_descriptions),
        )

        if interface_id not in self._clients:
            _LOGGER.warning(
                "ADD_NEW_DEVICES failed: Missing client for interface_id %s",
                interface_id,
            )
            return

        async with self._sema_add_devices:
            # We need this to avoid adding duplicates.
            known_addresses = tuple(
                dev_desc["ADDRESS"]
                for dev_desc in self._device_descriptions.get_raw_device_descriptions(
                    interface_id=interface_id
                )
            )
            client = self._clients[interface_id]
            save_paramset_descriptions = False
            save_device_descriptions = False
            for dev_desc in device_descriptions:
                try:
                    self._device_descriptions.add_device_description(
                        interface_id=interface_id, device_description=dev_desc
                    )
                    save_device_descriptions = True
                    if dev_desc["ADDRESS"] not in known_addresses:
                        await client.fetch_paramset_descriptions(device_description=dev_desc)
                        save_paramset_descriptions = True
                except Exception as ex:  # pragma: no cover
                    _LOGGER.error(
                        "ADD_NEW_DEVICES failed: %s [%s]",
                        type(ex).__name__,
                        reduce_args(args=ex.args),
                    )

            await self.save_caches(
                save_device_descriptions=save_device_descriptions,
                save_paramset_descriptions=save_paramset_descriptions,
            )
            if new_device_addresses := self._check_for_new_device_addresses():
                await self._device_details.load()
                await self._data_cache.load()
                await self._create_devices(new_device_addresses=new_device_addresses)

    def _check_for_new_device_addresses(self) -> dict[str, set[str]]:
        """Check if there are new devices, that needs to be created."""
        new_device_addresses: dict[str, set[str]] = {}
        for interface_id in self.interface_ids:
            if not self._paramset_descriptions.has_interface_id(interface_id=interface_id):
                _LOGGER.debug(
                    "CHECK_FOR_NEW_DEVICE_ADDRESSES: Skipping interface %s, missing paramsets",
                    interface_id,
                )
                continue

            if interface_id not in new_device_addresses:
                new_device_addresses[interface_id] = set()

            for device_address in self._device_descriptions.get_addresses(
                interface_id=interface_id
            ):
                if device_address not in self._devices:
                    new_device_addresses[interface_id].add(device_address)

            if not new_device_addresses[interface_id]:
                del new_device_addresses[interface_id]

        if _LOGGER.isEnabledFor(level=DEBUG):
            count: int = 0
            for item in new_device_addresses.values():
                count += len(item)

            _LOGGER.debug(
                "CHECK_FOR_NEW_DEVICE_ADDRESSES: %s: %i.",
                "Found new device addresses"
                if new_device_addresses
                else "Did not find any new device addresses",
                count,
            )

        return new_device_addresses

    @callback_event
    async def event(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """If a device emits some sort event, we will handle it here."""
        _LOGGER.debug(
            "EVENT: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )
        if not self.has_client(interface_id=interface_id):
            return

        self.last_events[interface_id] = datetime.now()
        # No need to check the response of a XmlRPC-PING
        if parameter == Parameter.PONG:
            if "#" in value:
                v_interface_id, v_timestamp = value.split("#")
                if (
                    v_interface_id == interface_id
                    and (client := self.get_client(interface_id=interface_id))
                    and client.supports_ping_pong
                ):
                    client.ping_pong_cache.handle_received_pong(
                        pong_ts=datetime.strptime(v_timestamp, DATETIME_FORMAT_MILLIS)
                    )
            return

        entity_key = get_entity_key(
            channel_address=channel_address,
            paramset_key=ParamsetKey.VALUES,
            parameter=parameter,
        )

        if entity_key in self._entity_event_subscriptions:
            try:
                for callback_handler in self._entity_event_subscriptions[entity_key]:
                    if callable(callback_handler):
                        await callback_handler(value)
            except RuntimeError as rte:  # pragma: no cover
                _LOGGER.debug(
                    "EVENT: RuntimeError [%s]. Failed to call callback for: %s, %s, %s",
                    reduce_args(args=rte.args),
                    interface_id,
                    channel_address,
                    parameter,
                )
            except Exception as ex:  # pragma: no cover
                _LOGGER.warning(
                    "EVENT failed: Unable to call callback for: %s, %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                    reduce_args(args=ex.args),
                )

    @callback_backend_system(system_event=BackendSystemEvent.LIST_DEVICES)
    def list_devices(self, interface_id: str) -> list[DeviceDescription]:
        """Return already existing devices to CCU / Homegear."""
        result = self._device_descriptions.get_raw_device_descriptions(interface_id=interface_id)
        _LOGGER.debug(
            "LIST_DEVICES: interface_id = %s, channel_count = %i", interface_id, len(result)
        )
        return result

    def add_event_subscription(self, entity: BaseParameterEntity) -> None:
        """Add entity to central event subscription."""
        if isinstance(entity, (GenericEntity, GenericEvent)) and entity.supports_events:
            if entity.entity_key not in self._entity_event_subscriptions:
                self._entity_event_subscriptions[entity.entity_key] = []
            self._entity_event_subscriptions[entity.entity_key].append(entity.event)

    @service()
    async def create_central_links(self) -> None:
        """Create a central links to support press events on all channels with click events."""
        for device in self.devices:
            await device.create_central_links()

    @service()
    async def remove_central_links(self) -> None:
        """Remove central links."""
        for device in self.devices:
            await device.remove_central_links()

    def remove_device(self, device: HmDevice) -> None:
        """Remove device to central collections."""
        if device.address not in self._devices:
            _LOGGER.debug(
                "REMOVE_DEVICE: device %s not registered in central",
                device.address,
            )
            return
        device.remove()

        self._device_descriptions.remove_device(device=device)
        self._paramset_descriptions.remove_device(device=device)
        self._device_details.remove_device(device=device)
        del self._devices[device.address]

    def remove_event_subscription(self, entity: BaseParameterEntity) -> None:
        """Remove event subscription from central collections."""
        if (
            isinstance(entity, (GenericEntity, GenericEvent))
            and entity.supports_events
            and entity.entity_key in self._entity_event_subscriptions
        ):
            del self._entity_event_subscriptions[entity.entity_key]

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""
        if client := self.primary_client:
            return await client.execute_program(pid=pid)  # type: ignore[no-any-return]
        return False

    async def fetch_sysvar_data(self, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        await self._hub.fetch_sysvar_data(scheduled=scheduled)

    async def fetch_program_data(self, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        await self._hub.fetch_program_data(scheduled=scheduled)

    @measure_execution_time
    async def load_and_refresh_entity_data(self, paramset_key: ParamsetKey | None = None) -> None:
        """Refresh entity data."""
        if paramset_key != ParamsetKey.MASTER and self._data_cache.is_empty:
            await self._data_cache.load()
        await self._data_cache.refresh_entity_data(paramset_key=paramset_key)

    async def get_system_variable(self, name: str) -> Any | None:
        """Get system variable from CCU / Homegear."""
        if client := self.primary_client:
            return await client.get_system_variable(name)
        return None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if entity := self.get_sysvar_entity(name=name):
            await entity.send_variable(value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self.name)

    async def set_install_mode(
        self,
        interface_id: str,
        on: bool = True,
        t: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Activate or deactivate install-mode on CCU / Homegear."""
        if not self.has_client(interface_id=interface_id):
            _LOGGER.warning(
                "SET_INSTALL_MODE: interface_id %s does not exist on %s",
                interface_id,
                self.name,
            )
            return False
        return await self.get_client(interface_id=interface_id).set_install_mode(  # type: ignore[no-any-return]
            on=on, t=t, mode=mode, device_address=device_address
        )

    def get_parameters(
        self,
        paramset_key: ParamsetKey,
        operations: tuple[Operations, ...],
        full_format: bool = False,
        un_ignore_candidates_only: bool = False,
        use_channel_wildcard: bool = False,
    ) -> list[str]:
        """Return all parameters from VALUES paramset."""
        parameters: set[str] = set()
        for channels in self._paramset_descriptions.raw_paramset_descriptions.values():
            for channel_address in channels:
                model: str | None = None
                if full_format:
                    model = self._device_descriptions.get_model(
                        device_address=get_device_address(address=channel_address)
                    )
                for parameter, parameter_data in (
                    channels[channel_address].get(paramset_key, {}).items()
                ):
                    if all(parameter_data["OPERATIONS"] & operation for operation in operations):
                        if un_ignore_candidates_only and (
                            (
                                (
                                    generic_entity := self.get_generic_entity(
                                        channel_address=channel_address,
                                        parameter=parameter,
                                        paramset_key=paramset_key,
                                    )
                                )
                                and generic_entity.enabled_default
                                and not generic_entity.is_un_ignored
                            )
                            or parameter in IGNORE_FOR_UN_IGNORE_PARAMETERS
                        ):
                            continue

                        if not full_format:
                            parameters.add(parameter)
                            continue

                        channel = (
                            UN_IGNORE_WILDCARD
                            if use_channel_wildcard
                            else get_channel_no(address=channel_address)
                        )

                        full_parameter = f"{parameter}:{paramset_key}@{model}:"
                        if channel is not None:
                            full_parameter += str(channel)
                        parameters.add(full_parameter)

        return list(parameters)

    def _get_virtual_remote(self, device_address: str) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for client in self._clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.address == device_address:
                return virtual_remote
        return None

    def get_generic_entity(
        self, channel_address: str, parameter: str, paramset_key: ParamsetKey | None = None
    ) -> GenericEntity | None:
        """Get entity by channel_address and parameter."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_entity(
                channel_address=channel_address, parameter=parameter, paramset_key=paramset_key
            )
        return None

    def get_event(self, channel_address: str, parameter: str) -> GenericEvent | None:
        """Return the hm event."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_event(channel_address=channel_address, parameter=parameter)
        return None

    def get_custom_entity(self, address: str, channel_no: int) -> CustomEntity | None:
        """Return the hm custom_entity."""
        if device := self.get_device(address=address):
            return device.get_custom_entity(channel_no=channel_no)
        return None

    def get_sysvar_entity(self, name: str) -> GenericSystemVariable | None:
        """Return the sysvar entity."""
        if sysvar := self._sysvar_entities.get(name):
            return sysvar
        for sysvar in self._sysvar_entities.values():
            if sysvar.name == name:
                return sysvar
        return None

    def get_program_button(self, pid: str) -> HmProgramButton | None:
        """Return the program button."""
        return self._program_buttons.get(pid)

    def get_un_ignore_candidates(self, include_master: bool = False) -> list[str]:
        """Return the candidates for un_ignore."""
        candidates = sorted(
            # 1. request simple parameter list for values parameters
            self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                un_ignore_candidates_only=True,
            )
            # 2. request full_format parameter list with channel wildcard for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
                use_channel_wildcard=True,
            )
            # 3. request full_format parameter list for values parameters
            + self.get_parameters(
                paramset_key=ParamsetKey.VALUES,
                operations=(Operations.READ, Operations.EVENT),
                full_format=True,
                un_ignore_candidates_only=True,
            )
        )
        if include_master:
            # 4. request full_format parameter list for master parameters
            candidates += sorted(
                self.get_parameters(
                    paramset_key=ParamsetKey.MASTER,
                    operations=(Operations.READ,),
                    full_format=True,
                    un_ignore_candidates_only=True,
                )
            )
        return candidates

    async def clear_caches(self) -> None:
        """Clear all stored data."""
        await self._device_descriptions.clear()
        await self._paramset_descriptions.clear()
        self._device_details.clear()
        self._data_cache.clear()

    def register_homematic_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register ha_event callback in central."""
        if callable(cb) and cb not in self._homematic_callbacks:
            self._homematic_callbacks.add(cb)
            return partial(self._unregister_homematic_callback, cb=cb)
        return None

    def _unregister_homematic_callback(self, cb: Callable) -> None:
        """RUn register ha_event callback in central."""
        if cb in self._homematic_callbacks:
            self._homematic_callbacks.remove(cb)

    @loop_check
    def fire_homematic_callback(
        self, event_type: HomematicEventType, event_data: dict[str, str]
    ) -> None:
        """
        Fire homematic_callback in central.

        # Events like INTERFACE, KEYPRESS, ...
        """
        for callback_handler in self._homematic_callbacks:
            try:
                callback_handler(event_type, event_data)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_HOMEMATIC_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_backend_parameter_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register backend_parameter callback in central."""
        if callable(cb) and cb not in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.add(cb)
            return partial(self._unregister_backend_parameter_callback, cb=cb)
        return None

    def _unregister_backend_parameter_callback(self, cb: Callable) -> None:
        """Un register backend_parameter callback in central."""
        if cb in self._backend_parameter_callbacks:
            self._backend_parameter_callbacks.remove(cb)

    @loop_check
    def fire_backend_parameter_callback(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Fire backend_parameter callback in central.

        Not used by HA.
        Re-Fired events from CCU for parameter updates.
        """
        for callback_handler in self._backend_parameter_callbacks:
            try:
                callback_handler(interface_id, channel_address, parameter, value)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_BACKEND_PARAMETER_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_backend_system_callback(self, cb: Callable) -> CALLBACK_TYPE:
        """Register system_event callback in central."""
        if callable(cb) and cb not in self._backend_parameter_callbacks:
            self._backend_system_callbacks.add(cb)
            return partial(self._unregister_backend_system_callback, cb=cb)
        return None

    def _unregister_backend_system_callback(self, cb: Callable) -> None:
        """Un register system_event callback in central."""
        if cb in self._backend_system_callbacks:
            self._backend_system_callbacks.remove(cb)

    @loop_check
    def fire_backend_system_callback(
        self, system_event: BackendSystemEvent, **kwargs: Any
    ) -> None:
        """
        Fire system_event callback in central.

        e.g. DEVICES_CREATED, HUB_REFRESHED
        """
        for callback_handler in self._backend_system_callbacks:
            try:
                callback_handler(system_event, **kwargs)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_BACKEND_SYSTEM_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central name: {self.name}"


class _ConnectionChecker(threading.Thread):
    """Periodically check Connection to CCU / Homegear."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the connection checker."""
        threading.Thread.__init__(self, name=f"ConnectionChecker for {central.name}")
        self._central: Final = central
        self._active = True
        self._central_is_connected = True

    def run(self) -> None:
        """Run the ConnectionChecker thread."""
        _LOGGER.debug(
            "run: Init connection checker to server %s",
            self._central.name,
        )
        while self._active:
            self._central.looper.run_coroutine(self._check_connection(), name="check_connection")
            if self._active:
                sleep(config.CONNECTION_CHECKER_INTERVAL)

    def stop(self) -> None:
        """To stop the ConnectionChecker."""
        self._active = False

    async def _check_connection(self) -> None:
        """Periodically check connection to backend."""
        _LOGGER.debug(
            "check_connection: Checking connection to server %s",
            self._central.name,
        )
        try:
            if not self._central.has_clients:
                _LOGGER.warning(
                    "CHECK_CONNECTION failed: No clients exist. "
                    "Trying to create clients for server %s",
                    self._central.name,
                )
                await self._central.restart_clients()
            else:
                reconnects: list[Any] = []
                for interface_id in self._central.interface_ids:
                    # check:
                    #  - client is available
                    #  - client is connected
                    #  - interface callback is alive
                    client = self._central.get_client(interface_id=interface_id)
                    if (
                        client.available is False
                        or not await client.is_connected()
                        or not client.is_callback_alive()
                    ):
                        reconnects.append(client.reconnect())
                if reconnects:
                    await asyncio.gather(*reconnects)
                    if self._central.available:
                        await self._central.load_and_refresh_entity_data()
        except NoConnection as nex:
            _LOGGER.error("CHECK_CONNECTION failed: no connection: %s", reduce_args(args=nex.args))
        except Exception as ex:
            _LOGGER.error(
                "CHECK_CONNECTION failed: %s [%s]",
                type(ex).__name__,
                reduce_args(args=ex.args),
            )


class CentralConfig:
    """Config for a Client."""

    def __init__(
        self,
        storage_folder: str,
        name: str,
        host: str,
        username: str,
        password: str,
        central_id: str,
        interface_configs: AbstractSet[hmcl.InterfaceConfig],
        default_callback_port: int,
        client_session: ClientSession | None,
        tls: bool = DEFAULT_TLS,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        callback_host: str | None = None,
        callback_port: int | None = None,
        json_port: int | None = None,
        listen_ip_addr: str | None = None,
        listen_port: int | None = None,
        max_read_workers: int = DEFAULT_MAX_READ_WORKERS,
        un_ignore_list: list[str] | None = None,
        program_scan_enabled: bool = DEFAULT_PROGRAM_SCAN_ENABLED,
        include_internal_programs: bool = DEFAULT_INCLUDE_INTERNAL_PROGRAMS,
        sysvar_scan_enabled: bool = DEFAULT_SYSVAR_SCAN_ENABLED,
        include_internal_sysvars: bool = DEFAULT_INCLUDE_INTERNAL_SYSVARS,
        start_direct: bool = False,
        base_path: str | None = None,
    ) -> None:
        """Init the client config."""
        self.connection_state: Final = CentralConnectionState()
        self.storage_folder: Final = storage_folder
        self.name: Final = name
        self.host: Final = host
        self.username: Final = username
        self.password: Final = password
        self.central_id: Final = central_id
        self.interface_configs: Final = interface_configs
        self.default_callback_port: Final = default_callback_port
        self.client_session: Final = client_session
        self.tls: Final = tls
        self.verify_tls: Final = verify_tls
        self.callback_host: Final = callback_host
        self.callback_port: Final = callback_port
        self.json_port: Final = json_port
        self.listen_ip_addr: Final = listen_ip_addr
        self.listen_port: Final = listen_port
        self.max_read_workers = max_read_workers
        self.un_ignore_list: Final = un_ignore_list
        self.program_scan_enabled: Final = program_scan_enabled
        self.include_internal_programs: Final = include_internal_programs
        self.sysvar_scan_enabled: Final = sysvar_scan_enabled
        self.include_internal_sysvars: Final = include_internal_sysvars
        self.start_direct: Final = start_direct
        self._json_rpc_client: JsonRpcAioHttpClient | None = None
        self._base_path: Final = base_path

    @property
    def central_url(self) -> str:
        """Return the required url."""
        url = "http://"
        if self.tls:
            url = "https://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    @property
    def enable_server(self) -> bool:
        """Return if server and connection checker should be started."""
        return self.start_direct is False

    @property
    def load_un_ignore(self) -> bool:
        """Return if un_ignore should be loaded."""
        return self.start_direct is False

    @property
    def use_caches(self) -> bool:
        """Return if caches should be used."""
        return self.start_direct is False

    @property
    def json_rpc_client(self) -> JsonRpcAioHttpClient:
        """Return the json rpx client."""
        if not self._json_rpc_client:
            self._json_rpc_client = JsonRpcAioHttpClient(
                username=self.username,
                password=self.password,
                device_url=self.central_url,
                connection_state=self.connection_state,
                client_session=self.client_session,
                tls=self.tls,
                verify_tls=self.verify_tls,
            )
        return self._json_rpc_client

    @property
    def base_path(self) -> str:
        """Return the path prefix."""
        if not self._base_path:
            return ""
        if self._base_path.endswith("/"):
            return self._base_path
        return f"{self._base_path}/"

    def check_config(self) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if config_failures := check_config(
            central_name=self.name,
            host=self.host,
            username=self.username,
            password=self.password,
            storage_folder=self.storage_folder,
            callback_host=self.callback_host,
            callback_port=self.callback_port,
            json_port=self.json_port,
        ):
            failures = ", ".join(config_failures)
            raise HaHomematicConfigException(failures)

    def create_central(self) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        try:
            self.check_config()
            return CentralUnit(self)
        except BaseHomematicException as ex:
            raise HaHomematicException(
                f"CREATE_CENTRAL: Not able to create a central: : {reduce_args(args=ex.args)}"
            ) from ex


class CentralConnectionState:
    """The central connection status."""

    def __init__(self) -> None:
        """Init the CentralConnectionStatus."""
        self._json_issues: Final[list[str]] = []
        self._xml_proxy_issues: Final[list[str]] = []

    def add_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and iid not in self._json_issues:
            self._json_issues.append(iid)
            _LOGGER.debug("add_issue: add issue  [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, XmlRpcProxy) and iid not in self._xml_proxy_issues:
            self._xml_proxy_issues.append(iid)
            _LOGGER.debug("add_issue: add issue [%s] for %s", iid, issuer.interface_id)
            return True
        return False

    def remove_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and iid in self._json_issues:
            self._json_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for JsonRpcAioHttpClient", iid)
            return True
        if isinstance(issuer, XmlRpcProxy) and issuer.interface_id in self._xml_proxy_issues:
            self._xml_proxy_issues.remove(iid)
            _LOGGER.debug("remove_issue: removing issue [%s] for %s", iid, issuer.interface_id)
            return True
        return False

    def has_issue(self, issuer: ConnectionProblemIssuer, iid: str) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient):
            return iid in self._json_issues
        if isinstance(issuer, XmlRpcProxy):
            return iid in self._xml_proxy_issues

    def handle_exception_log(
        self,
        issuer: ConnectionProblemIssuer,
        iid: str,
        exception: Exception,
        logger: logging.Logger = _LOGGER,
        level: int = logging.ERROR,
        extra_msg: str = "",
        multiple_logs: bool = True,
    ) -> None:
        """Handle Exception and derivates logging."""
        exception_name = (
            exception.name if hasattr(exception, "name") else exception.__class__.__name__
        )
        if self.has_issue(issuer=issuer, iid=iid) and multiple_logs is False:
            logger.debug(
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                reduce_args(args=exception.args),
                extra_msg,
            )
        else:
            self.add_issue(issuer=issuer, iid=iid)
            logger.log(
                level,
                "%s failed: %s [%s] %s",
                iid,
                exception_name,
                reduce_args(args=exception.args),
                extra_msg,
            )


def _get_new_entities(
    new_devices: set[HmDevice],
) -> Mapping[HmPlatform, AbstractSet[CallbackEntity]]:
    """Return new entities by platform."""

    entities_by_platform: dict[HmPlatform, set[CallbackEntity]] = {
        platform: set() for platform in PLATFORMS if platform != HmPlatform.EVENT
    }

    for device in new_devices:
        for platform in entities_by_platform:
            entities_by_platform[platform].update(
                device.get_entities(platform=platform, exclude_no_create=True, registered=False)
            )

    return entities_by_platform


def _get_new_channel_events(new_devices: set[HmDevice]) -> tuple[tuple[GenericEvent, ...], ...]:
    """Return new channel events by platform."""
    channel_events: list[tuple[GenericEvent, ...]] = []

    for device in new_devices:
        for event_type in ENTITY_EVENTS:
            if (
                hm_channel_events := list(
                    device.get_events(event_type=event_type, registered=False).values()
                )
            ) and len(hm_channel_events) > 0:
                channel_events.append(hm_channel_events)  # type: ignore[arg-type] # noqa:PERF401

    return tuple(channel_events)
