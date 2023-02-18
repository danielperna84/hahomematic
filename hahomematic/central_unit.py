"""
CentralUnit module.

This is the python representation of a CCU.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures._base import CancelledError
from datetime import datetime
import json
import logging
import socket
import threading
from typing import Any, Final, TypeVar

from aiohttp import ClientSession

from hahomematic import client as hmcl, config
from hahomematic.caches.dynamic import DeviceDataCache, DeviceDetailsCache
from hahomematic.caches.persistent import (
    DeviceDescriptionCache,
    ParamsetDescriptionCache,
)
from hahomematic.caches.visibility import ParameterVisibilityCache
from hahomematic.const import (
    ATTR_INTERFACE_ID,
    ATTR_TYPE,
    ATTR_VALUE,
    DEFAULT_TLS,
    DEFAULT_VERIFY_TLS,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HM_ADDRESS,
    IF_PRIMARY,
    LOCAL_INTERFACE,
    MAX_CACHE_AGE,
    PROXY_INIT_SUCCESS,
    HmEntityUsage,
    HmEventType,
    HmInterfaceEventType,
    HmPlatform,
)
from hahomematic.decorators import (
    async_callback_system_event,
    callback_event,
    callback_system_event,
)
from hahomematic.exceptions import (
    BaseHomematicException,
    HaHomematicException,
    NoClients,
    NoConnection,
)
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.platforms import create_entities_and_append_to_device
from hahomematic.platforms.custom.entity import CustomEntity
from hahomematic.platforms.device import HmDevice
from hahomematic.platforms.entity import BaseEntity
from hahomematic.platforms.event import GenericEvent
from hahomematic.platforms.generic.entity import GenericEntity
from hahomematic.platforms.hub import HmHub
from hahomematic.platforms.hub.button import HmProgramButton
from hahomematic.platforms.hub.entity import GenericHubEntity, GenericSystemVariable
from hahomematic.support import (
    check_or_create_directory,
    check_password,
    get_device_address,
)
from hahomematic.xml_rpc_proxy import XmlRpcProxy
import hahomematic.xml_rpc_server as xml_rpc

_LOGGER = logging.getLogger(__name__)
_R = TypeVar("_R")
_T = TypeVar("_T")

# {instance_name, central_unit}
CENTRAL_INSTANCES: Final[dict[str, CentralUnit]] = {}
ConnectionProblemIssuer = JsonRpcAioHttpClient | XmlRpcProxy


class CentralUnit:
    """Central unit that collects everything to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._sema_add_devices = asyncio.Semaphore()
        self._tasks: set[asyncio.Future[Any]] = set()
        # Keep the config for the central #CC
        self.config: Final[CentralConfig] = central_config
        self._attr_name: Final[str] = central_config.name
        self._attr_model: str | None = None
        self._connection_state: Final[CentralConnectionState] = central_config.connection_state
        self._loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        self._xml_rpc_server: xml_rpc.XmlRpcServer | None = None
        if central_config.enable_server:
            self._xml_rpc_server = xml_rpc.register_xml_rpc_server(
                local_port=central_config.callback_port or central_config.default_callback_port
            )
            self._xml_rpc_server.register_central(self)
        self.local_port: Final[int] = (
            self._xml_rpc_server.local_port if self._xml_rpc_server else 0
        )

        # Caches for CCU data
        self.device_data: Final[DeviceDataCache] = DeviceDataCache(central=self)
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

        # {interface_id, client}
        self._clients: Final[dict[str, hmcl.Client]] = {}
        # {{channel_address, parameter}, event_handle}
        self._entity_event_subscriptions: Final[dict[tuple[str, str], Any]] = {}
        # {unique_identifier, entity}
        self._entities: Final[dict[str, BaseEntity]] = {}
        # {device_address, device}
        self._devices: Final[dict[str, HmDevice]] = {}
        # {sysvar_name, sysvar_entity}
        self.sysvar_entities: Final[dict[str, GenericSystemVariable]] = {}
        # {sysvar_name, program_button}U
        self.program_entities: Final[dict[str, HmProgramButton]] = {}
        # store last event received datetime by interface
        self.last_events: Final[dict[str, datetime]] = {}
        # Signature: (name, *args) #CC
        self.callback_system_event: Callable | None = None
        # Signature: (interface_id, channel_address, value_key, value) #CC
        self.callback_entity_event: Callable | None = None
        # Signature: (interface_id, entity) #CC
        self.callback_entity_data_event: Callable | None = None
        # Signature: (event_type, event_data) #CC
        self.callback_ha_event: Callable | None = None

        self.json_rpc_client: Final[JsonRpcAioHttpClient] = central_config.create_json_rpc_client()

        CENTRAL_INSTANCES[self._attr_name] = self
        self._connection_checker: Final[ConnectionChecker] = ConnectionChecker(self)
        self._hub: HmHub = HmHub(central=self)
        self._attr_version: str | None = None

    @property
    def available(self) -> bool:
        """Return the availability of the central_unit."""
        return all(client.available for client in self._clients.values())

    @property
    def central_url(self) -> str:
        """Return the central_orl from config. #CC."""
        return self.config.central_url

    @property
    def devices(self) -> tuple[HmDevice, ...]:
        """Return a tuple of devices."""
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
    def interface_ids(self) -> list[str]:
        """Return all associated interfaces."""
        return list(self._clients)

    @property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return all(client.is_callback_alive() for client in self._clients.values())

    @property
    def model(self) -> str | None:
        """Return the model of the backend. #CC."""
        if not self._attr_model and (client := self.get_primary_client()):
            self._attr_model = client.model
        return self._attr_model

    @property
    def name(self) -> str:
        """Return the name of the backend. #CC."""
        return self._attr_name

    @property
    def serial(self) -> str | None:
        """Return the serial of the backend."""
        if client := self.get_primary_client():
            return client.serial
        return None

    @property
    def version(self) -> str | None:
        """Return the version of the backend. #CC."""
        if self._attr_version is None:
            versions: list[str] = []
            for client in self._clients.values():
                if client.version:
                    versions.append(client.version)
            self._attr_version = max(versions) if versions else None
        return self._attr_version

    async def start(self) -> None:
        """Start processing of the central unit. #CC."""
        await self.parameter_visibility.load()
        await self._start_clients()
        if self.config.enable_server:
            self._start_connection_checker()
        else:
            local_interface_id = f"{self.name}-{LOCAL_INTERFACE}"
            if self.has_client(interface_id=local_interface_id):
                client = self.get_client(interface_id=local_interface_id)
                if device_descriptions := await client.get_all_device_descriptions():
                    await self._add_new_devices(
                        interface_id=client.interface_id,
                        device_descriptions=device_descriptions,
                    )

    async def start_direct(self) -> None:
        """Start the central unit for temporary usage. #CC."""
        await self.parameter_visibility.load()
        await self._create_clients()
        for client in self._clients.values():
            if device_descriptions := await client.get_all_device_descriptions():
                await self._add_new_devices(
                    interface_id=client.interface_id,
                    device_descriptions=device_descriptions,
                )

    async def stop(self) -> None:
        """Stop processing of the central unit. #CC."""
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
        if self._attr_name in CENTRAL_INSTANCES:
            del CENTRAL_INSTANCES[self._attr_name]

        while self._has_active_threads:
            await asyncio.sleep(1)

    async def restart_clients(self) -> None:
        """Restart clients."""
        await self._stop_clients()
        await self._start_clients()

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
                self._attr_name,
            )
            return False
        if len(self.config.interface_configs) == 0:
            _LOGGER.warning(
                "CREATE_CLIENTS failed: No Interfaces for %s defined",
                self._attr_name,
            )
            return False

        local_ip = await self._identify_callback_ip(list(self.config.interface_configs)[0].port)
        for interface_config in self.config.interface_configs:
            try:
                if client := await hmcl.create_client(
                    central=self, interface_config=interface_config, local_ip=local_ip
                ):
                    if interface_config.interface not in await client.get_available_interfaces():
                        _LOGGER.debug(
                            "CREATE_CLIENTS failed: Interface: %s is not available for backend",
                            interface_config.interface,
                        )
                        continue
                    _LOGGER.debug(
                        "CREATE_CLIENTS: Adding client %s to %s",
                        client.interface_id,
                        self._attr_name,
                    )
                    self._clients[client.interface_id] = client
            except BaseHomematicException as ex:
                self.fire_interface_event(
                    interface_id=interface_config.interface_id,
                    interface_event_type=HmInterfaceEventType.PROXY,
                    available=False,
                )
                _LOGGER.warning(
                    "CREATE_CLIENTS failed: Unable to create client for central [%s]",
                    ex.args,
                )

        if self.has_clients:
            _LOGGER.debug(
                "CREATE_CLIENTS: All clients successfully created for %s",
                self._attr_name,
            )
            return True

        _LOGGER.warning("CREATE_CLIENTS failed for %s", self._attr_name)
        return False

    async def _init_clients(self) -> None:
        """Init clients of control unit, and start connection checker."""
        for client in self._clients.values():
            if await client.proxy_init() == PROXY_INIT_SUCCESS:
                _LOGGER.debug("INIT_CLIENTS: client for %s initialized", client.interface_id)

    async def _de_init_clients(self) -> None:
        """De-init clients."""
        for name, client in self._clients.items():
            if await client.proxy_de_init():
                _LOGGER.debug("STOP: Proxy de-initialized: %s", name)

    async def _init_hub(self) -> None:
        """Init the hub."""
        await self._hub.fetch_program_data()
        await self._hub.fetch_sysvar_data()

    def fire_interface_event(
        self,
        interface_id: str,
        interface_event_type: HmInterfaceEventType,
        available: bool,
    ) -> None:
        """Fire an event about the interface status."""
        event_data = {
            ATTR_INTERFACE_ID: interface_id,
            ATTR_TYPE: interface_event_type,
            ATTR_VALUE: available,
        }
        # pylint: disable=not-callable
        if callable(self.callback_ha_event):
            self.callback_ha_event(
                HmEventType.INTERFACE,
                event_data,
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
            self._attr_name,
        )
        self._connection_checker.start()

    def _stop_connection_checker(self) -> None:
        """Start the connection checker."""
        self._connection_checker.stop()
        _LOGGER.debug(
            "STOP_CONNECTION_CHECKER: Stopped connection_checker for %s",
            self._attr_name,
        )

    async def validate_config_and_get_serial(self) -> str | None:
        """Validate the central configuration. #CC."""
        try:
            if len(self.config.interface_configs) == 0:
                raise NoClients("validate_config: No clients defined.")

            local_ip = await self._identify_callback_ip(
                list(self.config.interface_configs)[0].port
            )
            serial: str | None = None
            for interface_config in self.config.interface_configs:
                client = await hmcl.create_client(
                    central=self, interface_config=interface_config, local_ip=local_ip
                )
                if not serial:
                    serial = await client.get_serial()
            return serial
        except Exception as ex:
            _LOGGER.warning(ex)
            raise

    def get_client(self, interface_id: str) -> hmcl.Client:
        """Return a client by interface_id. #CC."""
        if not self.has_client(interface_id=interface_id):
            raise HaHomematicException(
                f"get_client: interface_id {interface_id} " f"does not exist on {self._attr_name}"
            )
        return self._clients[interface_id]

    def get_device(self, device_address: str) -> HmDevice | None:
        """Return homematic device. #CC."""
        return self._devices.get(device_address)

    def get_entities_by_platform(
        self, platform: HmPlatform, existing_unique_ids: list[str] | None = None
    ) -> list[BaseEntity]:
        """Return all entities by platform. #CC."""
        if not existing_unique_ids:
            existing_unique_ids = []
        entities = []
        for entity in self._entities.values():
            if (
                entity.unique_identifier not in existing_unique_ids
                and entity.usage != HmEntityUsage.ENTITY_NO_CREATE
                and entity.platform == platform
            ):
                entities.append(entity)

        return entities

    def get_readable_entities(self) -> list[BaseEntity]:
        """Return a list of readable entities. This also includes custom entities."""
        readable_entities: list[BaseEntity] = []
        for entity in self._entities.values():
            if (isinstance(entity, GenericEntity) and entity.is_readable) or isinstance(
                entity, CustomEntity
            ):
                readable_entities.append(entity)
        return readable_entities

    def get_primary_client(self) -> hmcl.Client | None:
        """Return the client by interface_id or the first with a virtual remote."""
        client: hmcl.Client | None = None
        for client in self._clients.values():
            if isinstance(client, hmcl.ClientLocal):
                return client
            if client.interface in IF_PRIMARY and client.available:
                return client
        return client

    def get_hub_entities_by_platform(
        self, platform: HmPlatform, existing_unique_ids: list[str] | None = None
    ) -> list[GenericHubEntity]:
        """Return the hub entities by platform. #CC."""
        if not existing_unique_ids:
            existing_unique_ids = []
        hub_entities: list[GenericHubEntity] = []
        for program_entity in self.program_entities.values():
            if (
                program_entity.unique_identifier not in existing_unique_ids
                and program_entity.platform == platform
            ):
                hub_entities.append(program_entity)

        for sysvar_entity in self.sysvar_entities.values():
            if (
                sysvar_entity.unique_identifier not in existing_unique_ids
                and sysvar_entity.platform == platform
            ):
                hub_entities.append(sysvar_entity)
        return hub_entities

    def get_virtual_remotes(self) -> list[HmDevice]:
        """Get the virtual remote for the Client. #CC."""
        virtual_remotes: list[HmDevice] = []
        for client in self._clients.values():
            if virtual_remote := client.get_virtual_remote():
                virtual_remotes.append(virtual_remote)
        return virtual_remotes

    def has_client(self, interface_id: str) -> bool:
        """Check if client exists in central. #CC."""
        return interface_id in self._clients

    @property
    def has_clients(self) -> bool:
        """Check if clients exists in central. #CC."""
        count_client = len(self._clients)
        count_client_defined = len(self.config.interface_configs)
        return count_client > 0 and count_client == count_client_defined

    async def _load_caches(self) -> None:
        """Load files to caches."""
        try:
            await self.device_descriptions.load()
            await self.paramset_descriptions.load()
            await self.device_details.load()
            await self.device_data.load()
        except json.decoder.JSONDecodeError:  # pragma: no cover
            _LOGGER.warning("LOAD_CACHES failed: Unable to load caches for %s", self._attr_name)
            await self.clear_all_caches()

    async def _create_devices(self) -> None:
        """Trigger creation of the objects that expose the functionality."""
        if not self._clients:
            raise HaHomematicException(
                f"create_devices: "
                f"No clients initialized. Not starting central {self._attr_name}."
            )
        _LOGGER.debug("CREATE_DEVICES: Starting to create devices for %s", self._attr_name)

        new_devices = set[HmDevice]()
        for interface_id in self._clients:
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
                        err.args,
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
                        err.args,
                        interface_id,
                        device_address,
                    )
        _LOGGER.debug("CREATE_DEVICES: Finished creating devices for %s", self._attr_name)

        if (
            len(new_devices) > 0
            and self.callback_system_event is not None
            and callable(self.callback_system_event)
        ):
            # pylint: disable=not-callable
            self.callback_system_event(name=HH_EVENT_DEVICES_CREATED, new_devices=new_devices)

    async def delete_device(self, interface_id: str, device_address: str) -> None:
        """Delete devices from central_unit. #CC."""
        _LOGGER.debug(
            "DELETE_DEVICE: interface_id = %s, device_address = %s",
            interface_id,
            device_address,
        )

        if (device := self._devices.get(device_address)) is None:
            return
        addresses: list[str] = list(device.channels.keys())
        addresses.append(device_address)
        if len(addresses) == 0:
            _LOGGER.debug(
                "DELETE_DEVICE: Nothing to delete: interface_id = %s, device_address = %s",
                interface_id,
                device_address,
            )
            return

        await self.delete_devices(interface_id=interface_id, addresses=addresses)

    @async_callback_system_event(name=HH_EVENT_DELETE_DEVICES)
    async def delete_devices(self, interface_id: str, addresses: list[str]) -> None:
        """Delete devices from central_unit."""
        _LOGGER.debug(
            "DELETE_DEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        for address in addresses:
            if device := self._devices.get(address):
                await self.remove_device(device=device)

    @async_callback_system_event(name=HH_EVENT_NEW_DEVICES)
    async def add_new_devices(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """Add new devices to central unit."""
        await self._add_new_devices(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    async def _add_new_devices(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
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
            # We need this list to avoid adding duplicates.
            known_addresses = [
                dev_desc[HM_ADDRESS]
                for dev_desc in self.device_descriptions.get_raw_device_descriptions(interface_id)
            ]
            client = self._clients[interface_id]
            for dev_desc in device_descriptions:
                try:
                    if dev_desc[HM_ADDRESS] not in known_addresses:
                        self.device_descriptions.add_device_description(interface_id, dev_desc)
                        await client.fetch_paramset_descriptions(dev_desc)
                except Exception as err:  # pragma: no cover
                    _LOGGER.error("ADD_NEW_DEVICES failed: %s [%s]", type(err).__name__, err.args)

            await self.device_descriptions.save()
            await self.paramset_descriptions.save()
            await self.device_details.load()
            await self.device_data.load()
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
        if parameter == "PONG":
            return
        if (channel_address, parameter) in self._entity_event_subscriptions:
            try:
                for callback in self._entity_event_subscriptions[(channel_address, parameter)]:
                    callback(value)
            except RuntimeError as rte:  # pragma: no cover
                _LOGGER.debug(
                    "event: RuntimeError [%s]. Failed to call callback for: %s, %s, %s",
                    rte.args,
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
                    ex.args,
                )

    @callback_system_event(name=HH_EVENT_LIST_DEVICES)
    def list_devices(self, interface_id: str) -> list[dict[str, Any]]:
        """Return already existing devices to CCU / Homegear."""
        _LOGGER.debug("list_devices: interface_id = %s", interface_id)

        return self.device_descriptions.get_raw_device_descriptions(interface_id=interface_id)

    def add_entity(self, entity: BaseEntity) -> None:
        """Add entity to central collections."""
        if not isinstance(entity, GenericEvent):
            if entity.unique_identifier in self._entities:
                _LOGGER.warning(
                    "Entity %s already registered in central %s",
                    entity.unique_identifier,
                    self.name,
                )
                return
            self._entities[entity.unique_identifier] = entity

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
                "remove_device: device %s not registered in central",
                device.device_address,
            )
            return
        device.clear_collections()

        await self.device_descriptions.remove_device(device=device)
        await self.paramset_descriptions.remove_device(device=device)
        self.device_details.remove_device(device=device)
        del self._devices[device.device_address]

    def remove_entity(self, entity: BaseEntity) -> None:
        """Remove entity to central collections."""
        if entity.unique_identifier in self._entities:
            del self._entities[entity.unique_identifier]

        if (
            isinstance(entity, (GenericEntity, GenericEvent))
            and entity.supports_events
            and (entity.channel_address, entity.parameter) in self._entity_event_subscriptions
        ):
            del self._entity_event_subscriptions[(entity.channel_address, entity.parameter)]

    def has_entity(self, unique_identifier: str) -> bool:
        """Check if unique_identifier is already added."""
        return unique_identifier in self._entities

    def create_task(self, target: Awaitable) -> None:
        """Add task to the executor pool."""
        try:
            self._loop.call_soon_threadsafe(self._async_create_task, target)
        except CancelledError:
            _LOGGER.debug(
                "create_task: task cancelled for %s",
                self._attr_name,
            )
            return

    def _async_create_task(self, target: Coroutine[Any, Any, _R]) -> asyncio.Task[_R]:
        """Create a task from within the event_loop. This method must be run in the event_loop."""
        task = self._loop.create_task(target)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    def run_coroutine(self, coro: Coroutine) -> Any:
        """call coroutine from sync."""
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result()
        except CancelledError:  # pragma: no cover
            _LOGGER.debug(
                "run_coroutine: coroutine interrupted for %s",
                self._attr_name,
            )
            return None

    def async_add_executor_job(self, target: Callable[..., _T], *args: Any) -> asyncio.Future[_T]:
        """Add an executor job from within the event_loop."""
        try:
            task = self._loop.run_in_executor(None, target, *args)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)
            return task
        except (CancelledError, asyncio.TimeoutError) as err:  # pragma: no cover
            _LOGGER.debug(
                "async_add_executor_job: task cancelled for %s",
                self._attr_name,
            )
            raise HaHomematicException from err

    async def execute_program(self, pid: str) -> bool:
        """Execute a program on CCU / Homegear."""
        if client := self.get_primary_client():
            return await client.execute_program(pid=pid)
        return False

    async def fetch_sysvar_data(self, include_internal: bool = True) -> None:
        """fetch sysvar data for the hub. #CC."""
        await self._hub.fetch_sysvar_data(include_internal=include_internal)

    async def fetch_program_data(self, include_internal: bool = False) -> None:
        """fetch program data for the hub. #CC."""
        await self._hub.fetch_program_data(include_internal=include_internal)

    async def load_and_refresh_entity_data(
        self, paramset_key: str | None = None, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Refresh entity data. #CC."""
        if self.device_data.is_empty(max_age_seconds=max_age_seconds):
            await self.device_data.load()
        await self.device_data.refresh_entity_data(
            paramset_key=paramset_key, max_age_seconds=max_age_seconds
        )

    async def get_system_variable(self, name: str) -> Any | None:
        """Get system variable from CCU / Homegear."""
        if client := self.get_primary_client():
            return await client.get_system_variable(name)
        return None

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear.  #CC."""
        if entity := self.sysvar_entities.get(name):
            await entity.send_variable(value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self.name)

    # pylint: disable=invalid-name
    async def set_install_mode(
        self,
        interface_id: str,
        on: bool = True,
        t: int = 60,
        mode: int = 1,
        device_address: str | None = None,
    ) -> bool:
        """Activate or deactivate install-mode on CCU / Homegear. #CC."""
        if not self.has_client(interface_id=interface_id):
            _LOGGER.warning(
                "SET_INSTALL_MODE: interface_id %s does not exist on %s",
                interface_id,
                self._attr_name,
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
        """Get entity by channel_address and parameter. #CC."""
        if (
            ":" in channel_address
            and (device := self._devices.get(get_device_address(channel_address)))
            and (
                entity := device.get_generic_entity(
                    channel_address=channel_address, parameter=parameter
                )
            )
        ):
            return entity
        return None

    def clear_dynamic_caches(self) -> None:
        """Clear all stored data. #CC."""
        self.device_details.clear()
        self.device_data.clear()

    async def clear_all_caches(self) -> None:
        """Clear all stored data. #CC."""
        await self.device_descriptions.clear()
        await self.paramset_descriptions.clear()
        self.clear_dynamic_caches()


class ConnectionChecker(threading.Thread):
    """Periodically check Connection to CCU / Homegear."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the connection checker."""
        threading.Thread.__init__(self, name=f"ConnectionChecker for {central.name}")
        self._central: Final[CentralUnit] = central
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
                            # refresh cache
                            await self._central.device_data.load()
                            # refresh entity data
                            await self._central.device_data.refresh_entity_data()
            except NoConnection as nex:
                _LOGGER.error("CHECK_CONNECTION failed: no connection: %s", nex.args)
                continue
            except Exception as err:
                _LOGGER.error("CHECK_CONNECTION failed: %s [%s]", type(err).__name__, err.args)
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
        interface_configs: set[hmcl.InterfaceConfig],
        default_callback_port: int,
        client_session: ClientSession | None,
        tls: bool = DEFAULT_TLS,
        verify_tls: bool = DEFAULT_VERIFY_TLS,
        callback_host: str | None = None,
        callback_port: int | None = None,
        json_port: int | None = None,
        un_ignore_list: list[str] | None = None,
        use_caches: bool = True,
        load_un_ignore: bool = True,
    ) -> None:
        """Init the client config."""
        self.connection_state: Final[CentralConnectionState] = CentralConnectionState()
        self.storage_folder: Final[str] = storage_folder
        self.name: Final[str] = name
        self.host: Final[str] = host
        self.username: Final[str] = username
        self.password: Final[str] = password
        self.central_id: Final[str] = central_id
        self.interface_configs: Final[set[hmcl.InterfaceConfig]] = interface_configs
        self.default_callback_port: Final[int] = default_callback_port
        self.client_session: Final[ClientSession | None] = client_session
        self.tls: Final[bool] = tls
        self.verify_tls: Final[bool] = verify_tls
        self.callback_host: Final[str | None] = callback_host
        self.callback_port: Final[int | None] = callback_port
        self.json_port: Final[int | None] = json_port
        self.un_ignore_list: Final[list[str] | None] = un_ignore_list
        self._use_caches: Final[bool] = use_caches
        self._load_un_ignore: Final[bool] = load_un_ignore

    @property
    def central_url(self) -> str:
        """Return the required url. #CC."""
        url = "http://"
        if self.tls:
            url = "https://"
        url = f"{url}{self.host}"
        if self.json_port:
            url = f"{url}:{self.json_port}"
        return f"{url}"

    @property
    def enable_server(self) -> bool:
        """Return if xmlrpc-server should be started."""
        for interface_config in self.interface_configs:
            if interface_config.interface == LOCAL_INTERFACE:
                return False
        return True

    @property
    def load_un_ignore(self) -> bool:
        """Return if unignore should be loaded."""
        if not self.enable_server:
            return False
        return self._load_un_ignore

    @property
    def use_caches(self) -> bool:
        """Return if caches should be used."""
        if not self.enable_server:
            return False
        return self._use_caches

    def check_config(self) -> bool:
        """Check config."""
        if not self.username:
            _LOGGER.warning("CHECK_CONFIG: Username must not be empty")
            return False
        if self.password is None:
            _LOGGER.warning("CHECK_CONFIG: Password is required")  # type: ignore[unreachable]
            return False
        if not check_password(self.password):
            _LOGGER.warning("CHECK_CONFIG: password contains not allowed characters")
            # Here we only log a warning to get some feedback
            # no return False

        try:
            check_or_create_directory(self.storage_folder)
        except BaseHomematicException:
            _LOGGER.warning("CHECK_CONFIG: directory % cannot be created", self.storage_folder)
            return False
        return True

    async def create_central(self) -> CentralUnit:
        """Return the central."""
        if not self.check_config():
            raise HaHomematicException("create_central: Config contains errors. See log files.")
        return CentralUnit(self)

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
        self._json_issue: bool = False
        self._xml_proxy_issues: list[str] = []

    @property
    def outgoing_issue(self) -> bool:
        """Return if there is an outgoing connection issue."""
        return len(self._xml_proxy_issues) > 0

    def add_issue(self, issuer: ConnectionProblemIssuer) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and not self._json_issue:
            self._json_issue = True
            _LOGGER.debug("add_issue: add issue for JsonRpcAioHttpClient")
            return True
        if isinstance(issuer, XmlRpcProxy) and issuer.interface_id not in self._xml_proxy_issues:
            self._xml_proxy_issues.append(issuer.interface_id)
            _LOGGER.debug("add_issue: add issue for %s", issuer.interface_id)
            return True
        return False

    def remove_issue(self, issuer: ConnectionProblemIssuer) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient) and self._json_issue is True:
            self._json_issue = False
            _LOGGER.debug("remove_issue: removing issue for JsonRpcAioHttpClient")
            return True
        if isinstance(issuer, XmlRpcProxy) and issuer.interface_id in self._xml_proxy_issues:
            self._xml_proxy_issues.remove(issuer.interface_id)
            _LOGGER.debug("remove_issue: removing issue for %s", issuer.interface_id)
            return True
        return False

    def has_issue(self, issuer: ConnectionProblemIssuer) -> bool:
        """Add issue to collection."""
        if isinstance(issuer, JsonRpcAioHttpClient):
            return self._json_issue
        if isinstance(issuer, XmlRpcProxy):
            return issuer.interface_id in self._xml_proxy_issues
