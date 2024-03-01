"""
CentralUnit module.

This is the python representation of a CCU.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine, Mapping, Set
from concurrent.futures._base import CancelledError
from datetime import datetime
import logging
import socket
import threading
from typing import Any, Final, TypeVar, cast

from aiohttp import ClientSession
import orjson
import voluptuous as vol

from hahomematic import client as hmcl, config
from hahomematic.caches.dynamic import CentralDataCache, DeviceDetailsCache
from hahomematic.caches.persistent import DeviceDescriptionCache, ParamsetDescriptionCache
from hahomematic.caches.visibility import ParameterVisibilityCache
from hahomematic.central import xml_rpc_server as xmlrpc
from hahomematic.central.decorators import callback_event, callback_system_event
from hahomematic.client.json_rpc import JsonRpcAioHttpClient
from hahomematic.client.xml_rpc import XmlRpcProxy
from hahomematic.const import (
    DATETIME_FORMAT_MILLIS,
    DEFAULT_TLS,
    DEFAULT_VERIFY_TLS,
    ENTITY_EVENTS,
    EVENT_AVAILABLE,
    EVENT_DATA,
    EVENT_INTERFACE_ID,
    EVENT_TYPE,
    Description,
    DeviceFirmwareState,
    EventType,
    HmPlatform,
    InterfaceEventType,
    InterfaceName,
    Parameter,
    ParamsetKey,
    ProxyInitState,
    SystemEvent,
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
from hahomematic.platforms import create_entities_and_append_to_device
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.entity import BaseEntity, CallbackEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub import Hub
from hahomematic.platforms.hub.button import HmProgramButton
from hahomematic.platforms.hub.entity import GenericHubEntity, GenericSystemVariable
from hahomematic.support import check_config, get_device_address, reduce_args

_LOGGER: Final = logging.getLogger(__name__)

_R = TypeVar("_R")
_T = TypeVar("_T")

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


class CentralUnit:
    """Central unit that collects everything to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._started: bool = False
        self._sema_add_devices: Final = asyncio.Semaphore()
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        # Keep the config for the central
        self.config: Final = central_config
        self._name: Final = central_config.name
        self._model: str | None = None
        self._connection_state: Final = central_config.connection_state
        self._loop: Final = asyncio.get_running_loop()
        self._xml_rpc_server: Final = (
            xmlrpc.register_xml_rpc_server(
                local_port=central_config.callback_port or central_config.default_callback_port
            )
            if central_config.enable_server
            else None
        )
        if self._xml_rpc_server:
            self._xml_rpc_server.register_central(self)
        self.local_port: Final[int] = (
            self._xml_rpc_server.local_port if self._xml_rpc_server else 0
        )

        # Caches for CCU data
        self.data_cache: Final[CentralDataCache] = CentralDataCache(central=self)
        self.device_details: Final[DeviceDetailsCache] = DeviceDetailsCache(central=self)
        self.device_descriptions: Final[DeviceDescriptionCache] = DeviceDescriptionCache(
            central=self
        )
        self.paramset_descriptions: Final[ParamsetDescriptionCache] = ParamsetDescriptionCache(
            central=self
        )
        self.parameter_visibility: Final[ParameterVisibilityCache] = ParameterVisibilityCache(
            central=self
        )

        self._primary_client: hmcl.Client | None = None
        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        # {{channel_address, parameter}, event_handle}
        self._entity_event_subscriptions: Final[dict[tuple[str, str], Any]] = {}
        # {device_address, device}
        self._devices: Final[dict[str, HmDevice]] = {}
        # {sysvar_name, sysvar_entity}
        self._sysvar_entities: Final[dict[str, GenericSystemVariable]] = {}
        # {sysvar_name, program_button}U
        self._program_buttons: Final[dict[str, HmProgramButton]] = {}
        # store last event received datetime by interface
        self.last_events: Final[dict[str, datetime]] = {}
        # Signature: (name, *args)
        # e.g. DEVICES_CREATED, HUB_REFRESHED
        self._callback_system_event: Final[set[Callable]] = set()
        # Signature: (interface_id, channel_address, parameter, value)
        # Re-Fired events from CCU for parameter updates
        self._callback_entity_event: Final[set[Callable]] = set()
        # Signature: (interface_id, entity)
        # Fires parameter data updates as events with entity.
        self._callback_entity_data_event: Final[set[Callable]] = set()
        # Signature: (event_type, event_data)
        # Events like INTERFACE, KEYPRESS, ...
        self._callback_ha_event: Final[set[Callable]] = set()

        self.json_rpc_client: Final[JsonRpcAioHttpClient] = central_config.create_json_rpc_client()

        CENTRAL_INSTANCES[self._name] = self
        self._connection_checker: Final = ConnectionChecker(self)
        self._hub: Hub = Hub(central=self)
        self._version: str | None = None

    @property
    def available(self) -> bool:
        """Return the availability of the central."""
        return all(client.available for client in self._clients.values())

    @property
    def central_url(self) -> str:
        """Return the central_orl from config."""
        return self.config.central_url

    @property
    def clients(self) -> tuple[hmcl.Client, ...]:
        """Return all clients."""
        return tuple(self._clients.values())

    @property
    def devices(self) -> tuple[HmDevice, ...]:
        """Return all devices."""
        return tuple(self._devices.values())

    @property
    def _has_active_threads(self) -> bool:
        """Return if active sub threads are alive."""
        if self._connection_checker.is_alive():
            return True
        if (
            self._xml_rpc_server
            and self._xml_rpc_server.no_central_registered
            and self._xml_rpc_server.is_alive()
        ):
            return True
        return False

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
    def primary_client(self) -> hmcl.Client | None:
        """Return the primary client of the backend."""
        if self._primary_client is not None:
            return self._primary_client
        if client := self._get_primary_client():
            self._primary_client = client
        return self._primary_client

    @property
    def model(self) -> str | None:
        """Return the model of the backend."""
        if not self._model and (client := self.primary_client):
            self._model = client.model
        return self._model

    @property
    def name(self) -> str:
        """Return the name of the backend."""
        return self._name

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

    def add_sysvar_entity(self, sysvar_entity: GenericSystemVariable) -> None:
        """Add new program button."""
        if (ccu_var_name := sysvar_entity.ccu_var_name) is not None:
            self._sysvar_entities[ccu_var_name] = sysvar_entity

    def remove_sysvar_entity(self, name: str) -> None:
        """Remove a sysvar entity."""
        if (sysvar_entity := self.get_sysvar_entity(name=name)) is not None:
            sysvar_entity.fire_remove_entity_callback()
            del self._sysvar_entities[name]

    @property
    def program_buttons(self) -> tuple[HmProgramButton, ...]:
        """Return the program entities."""
        return tuple(self._program_buttons.values())

    def add_program_button(self, program_button: HmProgramButton) -> None:
        """Add new program button."""
        self._program_buttons[program_button.pid] = program_button

    def remove_program_button(self, pid: str) -> None:
        """Remove a program button."""
        if (program_button := self.get_program_button(pid=pid)) is not None:
            program_button.fire_remove_entity_callback()
            del self._program_buttons[pid]

    @property
    def version(self) -> str | None:
        """Return the version of the backend."""
        if self._version is None:
            versions: list[str] = []
            for client in self._clients.values():
                if client.version:
                    versions.append(client.version)
            self._version = max(versions) if versions else None
        return self._version

    async def start(self) -> None:
        """Start processing of the central unit."""
        if self._started:
            _LOGGER.debug("START: Central %s already started", self._name)
            return
        await self.parameter_visibility.load()
        if self.config.start_direct:
            if await self._create_clients():
                for client in self._clients.values():
                    await self._refresh_device_descriptions(client=client)
        else:
            await self._start_clients()
            if self.config.enable_server:
                self._start_connection_checker()
        self._started = True

    async def stop(self) -> None:
        """Stop processing of the central unit."""
        if not self._started:
            _LOGGER.debug("STOP: Central %s not started", self._name)
            return
        self._stop_connection_checker()
        await self._stop_clients()
        if self.json_rpc_client.is_activated:
            await self.json_rpc_client.logout()

        if self._xml_rpc_server:
            # un-register this instance from XmlRPC-Server
            self._xml_rpc_server.un_register_central(central=self)
            # un-register and stop XmlRPC-Server, if possible
            if self._xml_rpc_server.no_central_registered:
                self._xml_rpc_server.stop()
            _LOGGER.debug("STOP: XmlRPC-Server stopped")
        else:
            _LOGGER.debug(
                "STOP: shared XmlRPC-Server NOT stopped. "
                "There is still another central instance registered"
            )

        _LOGGER.debug("STOP: Removing instance")
        if self._name in CENTRAL_INSTANCES:
            del CENTRAL_INSTANCES[self._name]

        while self._has_active_threads:
            await asyncio.sleep(1)
        self._started = False

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._stop_clients()
        await self._start_clients()

    async def refresh_firmware_data(self, device_address: str | None = None) -> None:
        """Refresh device firmware data."""
        if device_address and (device := self.get_device(address=device_address)):
            await self._refresh_device_descriptions(
                client=device.client, device_address=device_address
            )
            device.refresh_firmware_data()
        else:
            for client in self._clients.values():
                await self._refresh_device_descriptions(client=client)
            for device in self._devices.values():
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
            await self.refresh_firmware_data(device_address=device.device_address)

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
            await self._create_devices()
            await self._init_hub()
            await self._init_clients()

    async def _stop_clients(self) -> None:
        """Stop clients."""
        await self._de_init_clients()
        for client in self._clients.values():
            _LOGGER.debug("STOP_CLIENTS: Stopping %s", client.interface_id)
            client.stop()
        _LOGGER.debug("STOP_CLIENTS: Clearing existing clients.")
        self._clients.clear()

    async def _create_clients(self) -> bool:
        """Create clients for the central unit. Start connection checker afterwards."""
        if len(self._clients) > 0:
            _LOGGER.warning(
                "CREATE_CLIENTS: Clients for %s are already created",
                self._name,
            )
            return False
        if len(self.config.interface_configs) == 0:
            _LOGGER.warning(
                "CREATE_CLIENTS failed: No Interfaces for %s defined",
                self._name,
            )
            return False

        local_ip = await self._identify_callback_ip(tuple(self.config.interface_configs)[0].port)
        for interface_config in self.config.interface_configs:
            try:
                if client := await hmcl.create_client(
                    central=self, interface_config=interface_config, local_ip=local_ip
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
                        self._name,
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
                self._name,
            )
            return True

        _LOGGER.debug("CREATE_CLIENTS failed for %s", self._name)
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
        await self._hub.fetch_program_data()
        await self._hub.fetch_sysvar_data()

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

        self.fire_ha_event_callback(
            event_type=EventType.INTERFACE,
            event_data=cast(dict[str, Any], INTERFACE_EVENT_SCHEMA(event_data)),
        )

    async def _identify_callback_ip(self, port: int) -> str:
        """Identify local IP used for callbacks."""

        # Do not add: pylint disable=no-member
        # This is only an issue on macOS
        def get_local_ip(host: str) -> str | None:
            """Get local_ip from socket."""
            try:
                socket.gethostbyname(host)
            except Exception as exc:
                message = f"GET_LOCAL_IP: Can't resolve host for {host}"
                _LOGGER.warning(message)
                raise HaHomematicException(message) from exc
            tmp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            tmp_socket.settimeout(config.TIMEOUT)
            tmp_socket.connect((host, port))
            local_ip = str(tmp_socket.getsockname()[0])
            tmp_socket.close()
            _LOGGER.debug("GET_LOCAL_IP: Got local ip: %s", local_ip)
            return local_ip

        callback_ip: str | None = None
        while callback_ip is None:
            try:
                callback_ip = await self.async_add_executor_job(get_local_ip, self.config.host)
            except HaHomematicException:
                callback_ip = "127.0.0.1"
            if callback_ip is None:
                _LOGGER.warning(
                    "GET_LOCAL_IP: Waiting for %i s,", config.CONNECTION_CHECKER_INTERVAL
                )
                await asyncio.sleep(config.CONNECTION_CHECKER_INTERVAL)

        return callback_ip

    def _start_connection_checker(self) -> None:
        """Start the connection checker."""
        _LOGGER.debug(
            "START_CONNECTION_CHECKER: Starting connection_checker for %s",
            self._name,
        )
        self._connection_checker.start()

    def _stop_connection_checker(self) -> None:
        """Start the connection checker."""
        self._connection_checker.stop()
        _LOGGER.debug(
            "STOP_CONNECTION_CHECKER: Stopped connection_checker for %s",
            self._name,
        )

    async def validate_config_and_get_system_information(self) -> SystemInformation:
        """Validate the central configuration."""
        try:
            if len(self.config.interface_configs) == 0:
                raise NoClients("validate_config: No clients defined.")

            local_ip = await self._identify_callback_ip(
                tuple(self.config.interface_configs)[0].port
            )
            system_information = SystemInformation()
            for interface_config in self.config.interface_configs:
                client = await hmcl.create_client(
                    central=self, interface_config=interface_config, local_ip=local_ip
                )
                if not system_information.serial:
                    system_information = client.system_information
            return system_information
        except NoClients:
            raise
        except Exception as ex:
            _LOGGER.warning(ex)
            raise

    def get_client(self, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id."""
        if not self.has_client(interface_id=interface_id):
            raise HaHomematicException(
                f"get_client: interface_id {interface_id} does not exist on {self._name}"
            )
        return self._clients[interface_id]

    def get_device(self, address: str) -> HmDevice | None:
        """Return homematic device."""
        d_address = get_device_address(address=address)
        return self._devices.get(d_address)

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
        self, paramset_key: str | None = None
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

    def get_channel_events(
        self, event_type: EventType, registered: bool | None = None
    ) -> tuple[list[GenericEvent], ...]:
        """Return all channel event entities."""
        hm_channel_events: list[list[GenericEvent]] = []
        for device in self.devices:
            for channel_events in device.get_channel_events(event_type=event_type).values():
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
        count_client_defined = len(self.config.interface_configs)
        return count_client > 0 and count_client == count_client_defined

    async def _load_caches(self) -> None:
        """Load files to caches."""
        try:
            await self.device_descriptions.load()
            await self.paramset_descriptions.load()
            await self.device_details.load()
            await self.data_cache.load()
        except orjson.JSONDecodeError:  # pragma: no cover
            _LOGGER.warning("LOAD_CACHES failed: Unable to load caches for %s", self._name)
            await self.clear_caches()

    async def _create_devices(self) -> None:
        """Trigger creation of the objects that expose the functionality."""
        if not self._clients:
            raise HaHomematicException(
                f"CREATE_DEVICES failed: No clients initialized. Not starting central {self._name}."
            )
        _LOGGER.debug("CREATE_DEVICES: Starting to create devices for %s", self._name)

        new_devices = set[HmDevice]()
        for interface_id in self.interface_ids:
            if not self.paramset_descriptions.has_interface_id(interface_id=interface_id):
                _LOGGER.debug(
                    "CREATE_DEVICES: Skipping interface %s, missing paramsets",
                    interface_id,
                )
                continue
            for device_address in self.device_descriptions.get_addresses(
                interface_id=interface_id
            ):
                # Do we check for duplicates here? For now, we do.
                device: HmDevice | None = None
                if device_address in self._devices:
                    continue
                try:
                    device = HmDevice(
                        central=self,
                        interface_id=interface_id,
                        device_address=device_address,
                    )

                except Exception as err:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create device: %s, %s",
                        type(err).__name__,
                        reduce_args(args=err.args),
                        interface_id,
                        device_address,
                    )
                try:
                    if device:
                        create_entities_and_append_to_device(device=device)
                        await device.load_value_cache()
                        new_devices.add(device)
                        self._devices[device_address] = device
                except Exception as err:  # pragma: no cover
                    _LOGGER.error(
                        "CREATE_DEVICES failed: %s [%s] Unable to create entities: %s, %s",
                        type(err).__name__,
                        reduce_args(args=err.args),
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self._name)

        if new_devices:
            new_entities = _get_new_entities(new_devices=new_devices)
            new_channel_events = _get_new_channel_events(new_devices=new_devices)
            self.fire_system_event_callback(
                system_event=SystemEvent.DEVICES_CREATED,
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
        addresses = device.channel_addresses
        addresses += (device_address,)

        await self.delete_devices(interface_id=interface_id, addresses=addresses)

    @callback_system_event(system_event=SystemEvent.DELETE_DEVICES)
    async def delete_devices(self, interface_id: str, addresses: tuple[str, ...]) -> None:
        """Delete devices from central."""
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        for address in addresses:
            if device := self._devices.get(address):
                await self.remove_device(device=device)

    @callback_system_event(system_event=SystemEvent.NEW_DEVICES)
    async def add_new_devices(
        self, interface_id: str, device_descriptions: tuple[dict[str, Any], ...]
    ) -> None:
        """Add new devices to central unit."""
        await self._add_new_devices(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    async def _add_new_devices(
        self, interface_id: str, device_descriptions: tuple[dict[str, Any], ...]
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
                dev_desc[Description.ADDRESS]
                for dev_desc in self.device_descriptions.get_raw_device_descriptions(interface_id)
            )
            client = self._clients[interface_id]
            for dev_desc in device_descriptions:
                try:
                    self.device_descriptions.add_device_description(interface_id, dev_desc)
                    if dev_desc[Description.ADDRESS] not in known_addresses:
                        await client.fetch_paramset_descriptions(dev_desc)
                except Exception as err:  # pragma: no cover
                    _LOGGER.error(
                        "ADD_NEW_DEVICES failed: %s [%s]",
                        type(err).__name__,
                        reduce_args(args=err.args),
                    )

            await self.device_descriptions.save()
            await self.paramset_descriptions.save()
            await self.device_details.load()
            await self.data_cache.load()
            await self._create_devices()

    @callback_event
    def event(self, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
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
                if v_interface_id == interface_id:
                    if (
                        client := self.get_client(interface_id=interface_id)
                    ) and client.supports_ping_pong:
                        client.ping_pong_cache.handle_received_pong(
                            pong_ts=datetime.strptime(v_timestamp, DATETIME_FORMAT_MILLIS)
                        )
            return
        if (channel_address, parameter) in self._entity_event_subscriptions:
            try:
                for callback in self._entity_event_subscriptions[(channel_address, parameter)]:
                    callback(value)
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

    @callback_system_event(system_event=SystemEvent.LIST_DEVICES)
    def list_devices(self, interface_id: str) -> list[dict[str, Any]]:
        """Return already existing devices to CCU / Homegear."""
        result = self.device_descriptions.get_raw_device_descriptions(interface_id=interface_id)
        _LOGGER.debug(
            "LIST_DEVICES: interface_id = %s, channel_count = %i", interface_id, len(result)
        )
        return result

    def add_event_subscription(self, entity: BaseEntity) -> None:
        """Add entity to central event subscription."""
        if isinstance(entity, (GenericEntity, GenericEvent)) and entity.supports_events:
            if (
                entity.channel_address,
                entity.parameter,
            ) not in self._entity_event_subscriptions:
                self._entity_event_subscriptions[(entity.channel_address, entity.parameter)] = []
            self._entity_event_subscriptions[(entity.channel_address, entity.parameter)].append(
                entity.event
            )

    async def remove_device(self, device: HmDevice) -> None:
        """Remove device to central collections."""
        if device.device_address not in self._devices:
            _LOGGER.debug(
                "REMOVE_DEVICE: device %s not registered in central",
                device.device_address,
            )
            return
        device.clear_collections()

        await self.device_descriptions.remove_device(device=device)
        await self.paramset_descriptions.remove_device(device=device)
        self.device_details.remove_device(device=device)
        del self._devices[device.device_address]

    def remove_event_subscription(self, entity: BaseEntity) -> None:
        """Remove event subscription from central collections."""
        if (
            isinstance(entity, (GenericEntity, GenericEvent))
            and entity.supports_events
            and (entity.channel_address, entity.parameter) in self._entity_event_subscriptions
        ):
            del self._entity_event_subscriptions[(entity.channel_address, entity.parameter)]

    def create_task(self, target: Awaitable, name: str) -> None:
        """Add task to the executor pool."""
        try:
            self._loop.call_soon_threadsafe(self._async_create_task, target, name)
        except CancelledError:
            _LOGGER.debug(
                "create_task: task cancelled for %s",
                self._name,
            )
            return

    def _async_create_task(self, target: Coroutine[Any, Any, _R], name: str) -> asyncio.Task[_R]:
        """Create a task from within the event_loop. This method must be run in the event_loop."""
        task = self._loop.create_task(target, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    def run_coroutine(self, coro: Coroutine) -> Any:
        """Call coroutine from sync."""
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result()
        except CancelledError:  # pragma: no cover
            _LOGGER.debug(
                "run_coroutine: coroutine interrupted for %s",
                self._name,
            )
            return None

    def async_add_executor_job(self, target: Callable[..., _T], *args: Any) -> asyncio.Future[_T]:
        """Add an executor job from within the event_loop."""
        try:
            task = self._loop.run_in_executor(None, target, *args)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)
            return task
        except (TimeoutError, CancelledError) as err:  # pragma: no cover
            message = f"async_add_executor_job: task cancelled for {self._name} [{reduce_args(args=err.args)}]"
            _LOGGER.debug(message)
            raise HaHomematicException(message) from err

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""
        if client := self.primary_client:
            return await client.execute_program(pid=pid)
        return False

    async def fetch_sysvar_data(self, include_internal: bool = True) -> None:
        """Fetch sysvar data for the hub."""
        await self._hub.fetch_sysvar_data(include_internal=include_internal)

    async def fetch_program_data(self, include_internal: bool = False) -> None:
        """Fetch program data for the hub."""
        await self._hub.fetch_program_data(include_internal=include_internal)

    @measure_execution_time
    async def load_and_refresh_entity_data(self, paramset_key: str | None = None) -> None:
        """Refresh entity data."""
        if paramset_key != ParamsetKey.MASTER and self.data_cache.is_empty:
            await self.data_cache.load()
        await self.data_cache.refresh_entity_data(paramset_key=paramset_key)

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
                self._name,
            )
            return False
        return await self.get_client(interface_id=interface_id).set_install_mode(
            on=on, t=t, mode=mode, device_address=device_address
        )

    def _get_virtual_remote(self, device_address: str) -> HmDevice | None:
        """Get the virtual remote for the Client."""
        for client in self._clients.values():
            virtual_remote = client.get_virtual_remote()
            if virtual_remote and virtual_remote.device_address == device_address:
                return virtual_remote
        return None

    def get_generic_entity(self, channel_address: str, parameter: str) -> GenericEntity | None:
        """Get entity by channel_address and parameter."""
        if device := self.get_device(address=channel_address):
            return device.get_generic_entity(channel_address=channel_address, parameter=parameter)
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

    async def clear_caches(self) -> None:
        """Clear all stored data."""
        await self.device_descriptions.clear()
        await self.paramset_descriptions.clear()
        self.device_details.clear()
        self.data_cache.clear()

    def register_ha_event_callback(self, callback_handler: Callable) -> None:
        """Register ha_event callback in central."""
        self._callback_ha_event.add(callback_handler)

    def unregister_ha_event_callback(self, callback_handler: Callable) -> None:
        """RUn register ha_event callback in central."""
        if callback_handler in self._callback_ha_event:
            self._callback_ha_event.remove(callback_handler)

    def fire_ha_event_callback(self, event_type: EventType, event_data: dict[str, str]) -> None:
        """
        Fire ha_event callback in central.

        # Events like INTERFACE, KEYPRESS, ...
        """
        for callback_handler in self._callback_ha_event:
            try:
                callback_handler(event_type, event_data)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_HA_EVENT_CALLBACK: Unable to call handler: %s", reduce_args(args=ex.args)
                )

    def register_entity_event_callback(self, callback_handler: Callable) -> None:
        """Register entity_event callback in central."""
        self._callback_entity_event.add(callback_handler)

    def unregister_entity_event_callback(self, callback_handler: Callable) -> None:
        """Un register entity_event callback in central."""
        if callback_handler in self._callback_entity_event:
            self._callback_entity_event.remove(callback_handler)

    def fire_entity_event_callback(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        Fire entity callback in central.

        Not used by HA.
        Re-Fired events from CCU for parameter updates.
        """
        for callback_handler in self._callback_entity_event:
            try:
                callback_handler(interface_id, channel_address, parameter, value)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_ENTITY_EVENT_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_entity_data_event_callback(self, callback_handler: Callable) -> None:
        """Register entity_event callback in central."""
        self._callback_entity_data_event.add(callback_handler)

    def unregister_entity_data_event_callback(self, callback_handler: Callable) -> None:
        """Un register entity_event callback in central."""
        if callback_handler in self._callback_entity_data_event:
            self._callback_entity_data_event.remove(callback_handler)

    def fire_entity_data_event_callback(self, interface_id: str, entity: BaseEntity) -> None:
        """
        Fire entity_data callback in central.

        Not used by HA.
        Fires parameter data updates as events with entity.
        """
        for callback_handler in self._callback_entity_data_event:
            try:
                callback_handler(interface_id, entity)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_ENTITY_DATA_EVENT_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def register_system_event_callback(self, callback_handler: Callable) -> None:
        """Register system_event callback in central."""
        self._callback_system_event.add(callback_handler)

    def unregister_system_event_callback(self, callback_handler: Callable) -> None:
        """Un register system_event callback in central."""
        if callback_handler in self._callback_system_event:
            self._callback_system_event.remove(callback_handler)

    def fire_system_event_callback(self, system_event: SystemEvent, **kwargs: Any) -> None:
        """
        Fire system_event callback in central.

        e.g. DEVICES_CREATED, HUB_REFRESHED
        """
        for callback_handler in self._callback_system_event:
            try:
                callback_handler(system_event, **kwargs)
            except Exception as ex:
                _LOGGER.error(
                    "FIRE_SYSTEM_EVENT_CALLBACK: Unable to call handler: %s",
                    reduce_args(args=ex.args),
                )

    def __str__(self) -> str:
        """Provide some useful information."""
        return f"central name: {self.name}"


class ConnectionChecker(threading.Thread):
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

        self._central.run_coroutine(self._check_connection())

    def stop(self) -> None:
        """To stop the ConnectionChecker."""
        self._active = False

    async def _check_connection(self) -> None:
        """Periodically check connection to backend."""
        while self._active:
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
                _LOGGER.error(
                    "CHECK_CONNECTION failed: no connection: %s", reduce_args(args=nex.args)
                )
                continue
            except Exception as err:
                _LOGGER.error(
                    "CHECK_CONNECTION failed: %s [%s]",
                    type(err).__name__,
                    reduce_args(args=err.args),
                )
            if self._active:
                await asyncio.sleep(config.CONNECTION_CHECKER_INTERVAL)


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
        interface_configs: Set[hmcl.InterfaceConfig],
        default_callback_port: int,
        client_session: ClientSession | None,
        tls: bool = DEFAULT_TLS,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        callback_host: str | None = None,
        callback_port: int | None = None,
        json_port: int | None = None,
        un_ignore_list: list[str] | None = None,
        start_direct: bool = False,
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
        self.un_ignore_list: Final = un_ignore_list
        self.start_direct = start_direct

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
        """Return if unignore should be loaded."""
        return self.start_direct is False

    @property
    def use_caches(self) -> bool:
        """Return if caches should be used."""
        return self.start_direct is False

    def check_config(self, extended_validation: bool = True) -> None:
        """Check config. Throws BaseHomematicException on failure."""
        if config_failures := check_config(
            central_name=self.name,
            username=self.username,
            password=self.password,
            storage_folder=self.storage_folder,
            extended_validation=extended_validation,
        ):
            failures = ", ".join(config_failures)
            raise HaHomematicConfigException(failures)

    def create_central(self, extended_validation: bool = True) -> CentralUnit:
        """Create the central. Throws BaseHomematicException on validation failure."""
        try:
            self.check_config(extended_validation=extended_validation)
            return CentralUnit(self)
        except BaseHomematicException as bhex:
            _LOGGER.warning("CREATE_CENTRAL: Not able to create a central: %s", bhex)
            raise

    def create_json_rpc_client(self) -> JsonRpcAioHttpClient:
        """Return the json rpc client."""
        return JsonRpcAioHttpClient(
            username=self.username,
            password=self.password,
            device_url=self.central_url,
            connection_state=self.connection_state,
            client_session=self.client_session,
            tls=self.tls,
            verify_tls=self.verify_tls,
        )


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
) -> Mapping[HmPlatform, Set[CallbackEntity]]:
    """Return new entities by platform."""
    entities_by_platform: dict[HmPlatform, set[CallbackEntity]] = {}
    for platform in HmPlatform:
        if platform == HmPlatform.EVENT:
            continue
        entities_by_platform[platform] = set()

    for device in new_devices:
        for platform, entities in device.get_entities_by_platform(
            exclude_no_create=True, registered=False
        ).items():
            entities_by_platform[platform].update(entities)

    return entities_by_platform


def _get_new_channel_events(new_devices: set[HmDevice]) -> tuple[list[GenericEvent], ...]:
    """Return new channel events by platform."""
    channel_events: list[list[GenericEvent]] = []

    for device in new_devices:
        for event_type in ENTITY_EVENTS:
            if hm_channel_events := device.get_channel_events(
                event_type=event_type, registered=False
            ).values():
                channel_events.append(hm_channel_events)  # type: ignore[arg-type]

    return tuple(channel_events)
