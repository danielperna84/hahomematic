"""
CentralUnit module.

This is the python representation of a CCU.
"""
from __future__ import annotations

from abc import ABC
import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from concurrent.futures._base import CancelledError
from dataclasses import dataclass
from datetime import datetime
import json
import logging
import os
import socket
import threading
from typing import Any, Final, TypeVar

from aiohttp import ClientSession

from hahomematic import config
import hahomematic.client as hmcl
from hahomematic.const import (
    ATTR_INTERFACE_ID,
    ATTR_TYPE,
    ATTR_VALUE,
    DEFAULT_ENCODING,
    DEFAULT_TLS,
    DEFAULT_VERIFY_TLS,
    FILE_DEVICES,
    FILE_PARAMSETS,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HM_ADDRESS,
    HM_OPERATIONS,
    HM_TYPE,
    IF_BIDCOS_RF_NAME,
    IF_PRIMARY,
    INIT_DATETIME,
    LOCAL_INTERFACE,
    MAX_CACHE_AGE,
    NO_CACHE_ENTRY,
    OPERATION_EVENT,
    OPERATION_READ,
    PARAMSET_KEY_VALUES,
    PROXY_INIT_SUCCESS,
    HmCallSource,
    HmDataOperationResult,
    HmEntityUsage,
    HmEventType,
    HmInterfaceEventType,
    HmPlatform,
)
from hahomematic.decorators import (
    async_callback_system_event,
    callback_event,
    callback_system_event,
    config_property,
    value_property,
)
from hahomematic.device import HmDevice
from hahomematic.entity import (
    BaseEntity,
    CustomEntity,
    GenericEntity,
    GenericEvent,
    GenericHubEntity,
    GenericSystemVariable,
)
from hahomematic.exceptions import (
    BaseHomematicException,
    HaHomematicException,
    NoClients,
    NoConnection,
)
from hahomematic.generic_platforms.button import HmProgramButton
from hahomematic.helpers import (
    check_or_create_directory,
    check_password,
    get_device_address,
    get_device_channel,
    updated_within_seconds,
)
from hahomematic.hub import HmHub
from hahomematic.json_rpc_client import JsonRpcAioHttpClient
from hahomematic.parameter_visibility import ParameterVisibilityCache
from hahomematic.xml_rpc_proxy import XmlRpcProxy
import hahomematic.xml_rpc_server as xml_rpc

_LOGGER = logging.getLogger(__name__)
T = TypeVar("T")

# {instance_name, central_unit}
CENTRAL_INSTANCES: dict[str, CentralUnit] = {}
ConnectionProblemIssuer = JsonRpcAioHttpClient | XmlRpcProxy


class CentralUnit:
    """Central unit that collects everything to handle communication from/to CCU/Homegear."""

    def __init__(self, central_config: CentralConfig) -> None:
        """Init the central unit."""
        self._sema_add_devices = asyncio.Semaphore()
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
        # Signature: (event_type, event_data) #CC
        self.callback_ha_event: Callable | None = None

        self.json_rpc_client: Final[JsonRpcAioHttpClient] = central_config.create_json_rpc_client()

        CENTRAL_INSTANCES[self._attr_name] = self
        self._connection_checker: Final[ConnectionChecker] = ConnectionChecker(self)
        self._hub: HmHub = HmHub(central=self)
        self._attr_version: str | None = None

    @value_property
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

    @value_property
    def is_alive(self) -> bool:
        """Return if XmlRPC-Server is alive."""
        return all(client.is_callback_alive() for client in self._clients.values())

    @config_property
    def model(self) -> str | None:
        """Return the model of the backend. #CC."""
        if not self._attr_model and (client := self.get_primary_client()):
            self._attr_model = client.model
        return self._attr_model

    @config_property
    def name(self) -> str:
        """Return the name of the backend. #CC."""
        return self._attr_name

    @config_property
    def serial(self) -> str | None:
        """Return the serial of the backend."""
        if client := self.get_primary_client():
            return client.serial
        return None

    @config_property
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
                callback_ip = await self.async_add_executor_job(
                    get_local_ip, self.config.host, timeout=10
                )
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
            await self.clear_all()

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
                        device.create_entities_and_append_to_device()
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
        """Check if unique_identifier is alread added."""
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

    def _async_create_task(self, target: Coroutine) -> asyncio.Task:
        """Create a task from within the event_loop. This method must be run in the event_loop."""
        return self._loop.create_task(target)

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

    async def async_add_executor_job(
        self, executor_func: Callable[..., T], *args: Any, timeout: int | None = None
    ) -> T:
        """Add an executor job from within the event_loop."""
        try:
            future = self._loop.run_in_executor(None, executor_func, *args)
            if timeout:
                return await asyncio.wait_for(future, timeout)
            return await future
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

    async def refresh_entity_data(
        self, paramset_key: str | None = None, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Refresh entity data. #CC."""
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

    async def clear_all(self) -> None:
        """Clear all stored data. #CC."""
        await self.device_descriptions.clear()
        await self.paramset_descriptions.clear()
        await self.device_details.clear()
        await self.device_data.clear()


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


class DeviceDetailsCache:
    """Cache for device/channel details."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the device details cache."""
        # {address, name}
        self._names_cache: Final[dict[str, str]] = {}
        self._interface_cache: Final[dict[str, str]] = {}
        self.device_channel_ids: Final[dict[str, str]] = {}
        self._channel_rooms: dict[str, set[str]] = {}
        self._device_room: Final[dict[str, str]] = {}
        self._functions: dict[str, set[str]] = {}
        self._central: Final[CentralUnit] = central

    async def load(self) -> None:
        """Fetch names from backend."""
        _LOGGER.debug("load: Loading names for %s", self._central.name)
        if client := self._central.get_primary_client():
            await client.fetch_device_details()
        _LOGGER.debug("load: Loading rooms for %s", self._central.name)
        self._channel_rooms = await self._get_all_rooms()
        self._identify_device_room()
        _LOGGER.debug("load: Loading functions for %s", self._central.name)
        self._functions = await self._get_all_functions()

    def add_name(self, address: str, name: str) -> None:
        """Add name to cache."""
        if address not in self._names_cache:
            self._names_cache[address] = name

    def get_name(self, address: str) -> str | None:
        """Get name from cache."""
        return self._names_cache.get(address)

    def add_interface(self, address: str, interface: str) -> None:
        """Add interface to cache."""
        if address not in self._interface_cache:
            self._interface_cache[address] = interface

    def get_interface(self, address: str) -> str:
        """Get interface from cache."""
        return self._interface_cache.get(address) or IF_BIDCOS_RF_NAME

    def add_device_channel_id(self, address: str, channel_id: str) -> None:
        """Add channel id for a channel."""
        self.device_channel_ids[address] = channel_id

    async def _get_all_rooms(self) -> dict[str, set[str]]:
        """Get all rooms, if available."""
        if client := self._central.get_primary_client():
            return await client.get_all_rooms()
        return {}

    def get_room(self, device_address: str) -> str | None:
        """Return room by device_address."""
        return self._device_room.get(device_address)

    async def _get_all_functions(self) -> dict[str, set[str]]:
        """Get all functions, if available."""
        if client := self._central.get_primary_client():
            return await client.get_all_functions()
        return {}

    def get_function_text(self, address: str) -> str | None:
        """Return function by address."""
        if functions := self._functions.get(address):
            return ",".join(functions)
        return None

    def remove_device(self, device: HmDevice) -> None:
        """Remove name from cache."""
        if device.device_address in self._names_cache:
            del self._names_cache[device.device_address]
        for channel_address in device.channels:
            if channel_address in self._names_cache:
                del self._names_cache[channel_address]

    async def clear(self) -> None:
        """Clear the cache."""
        self._names_cache.clear()
        self._channel_rooms.clear()
        self._functions.clear()

    def _identify_device_room(self) -> None:
        """
        Identify a possible room of a device.

        A room is relevant for a device, if there is only one room assigned to the channels.
        """
        device_rooms: dict[str, set[str]] = {}
        for address, rooms in self._channel_rooms.items():
            device_address = get_device_address(address=address)
            if device_address not in device_rooms:
                device_rooms[device_address] = set()
            device_rooms[device_address].update(rooms)
        for device_address, rooms in device_rooms.items():
            if rooms and len(set(rooms)) == 1:
                self._device_room[device_address] = list(set(rooms))[0]


class DeviceDataCache:
    """Cache for device/channel initial data."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the device data cache."""
        self._central: Final[CentralUnit] = central
        # { interface, {channel_address, {parameter, CacheEntry}}}
        self._central_values_cache: dict[str, dict[str, dict[str, Any]]] = {}
        self._last_updated = INIT_DATETIME

    @property
    def is_empty(self) -> bool:
        """Return if cache is empty."""
        return len(self._central_values_cache) == 0

    async def load(self) -> None:
        """Fetch device data from backend."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching device data for %s", self._central.name)
            return
        _LOGGER.debug("load: device data for %s", self._central.name)
        if client := self._central.get_primary_client():
            await client.fetch_all_device_data()

    async def refresh_entity_data(
        self, paramset_key: str | None = None, max_age_seconds: int = MAX_CACHE_AGE
    ) -> None:
        """Refresh entity data."""
        for entity in self._central.get_readable_entities():
            if paramset_key is None or (
                isinstance(entity, GenericEntity) and entity.paramset_key == paramset_key
            ):
                await entity.load_entity_value(
                    call_source=HmCallSource.HM_INIT,
                    max_age_seconds=max_age_seconds,
                )

    def add_device_data(self, device_data: dict[str, dict[str, dict[str, Any]]]) -> None:
        """Add device data to cache."""
        self._central_values_cache = device_data
        self._last_updated = datetime.now()

    def get_device_data(
        self,
        interface: str,
        channel_address: str,
        parameter: str,
        max_age_seconds: int,
    ) -> Any:
        """Get device data from cache."""
        if not self.is_empty and updated_within_seconds(
            last_update=self._last_updated, max_age_seconds=max_age_seconds
        ):
            return (
                self._central_values_cache.get(interface, {})
                .get(channel_address, {})
                .get(parameter, NO_CACHE_ENTRY)
            )
        return NO_CACHE_ENTRY

    async def clear(self) -> None:
        """Clear the cache."""
        self._central_values_cache.clear()


class BasePersistentCache(ABC):
    """Cache for files."""

    def __init__(
        self,
        central: CentralUnit,
        filename: str,
        persistant_cache: dict[str, Any],
    ) -> None:
        """Init the base class of the persistent cache."""
        self._central: Final[CentralUnit] = central
        self._cache_dir: Final[str] = f"{central.config.storage_folder}/cache"
        self._filename: Final[str] = f"{central.name}_{filename}"
        self._persistant_cache: Final[dict[str, Any]] = persistant_cache
        self.last_save: datetime = INIT_DATETIME

    async def save(self) -> HmDataOperationResult:
        """Save current name data in NAMES to disk."""

        def _save() -> HmDataOperationResult:
            if not check_or_create_directory(self._cache_dir):
                return HmDataOperationResult.NO_SAVE

            self.last_save = datetime.now()
            if self._central.config.use_caches:
                with open(
                    file=os.path.join(self._cache_dir, self._filename),
                    mode="w",
                    encoding=DEFAULT_ENCODING,
                ) as fptr:
                    json.dump(self._persistant_cache, fptr)
                return HmDataOperationResult.SAVE_SUCCESS

            _LOGGER.debug("save: not saving cache for %s", self._central.name)
            return HmDataOperationResult.NO_SAVE

        return await self._central.async_add_executor_job(_save)

    async def load(self) -> HmDataOperationResult:
        """Load file from disk into dict."""

        def _load() -> HmDataOperationResult:
            if not check_or_create_directory(self._cache_dir):
                return HmDataOperationResult.NO_LOAD
            if not os.path.exists(os.path.join(self._cache_dir, self._filename)):
                return HmDataOperationResult.NO_LOAD
            with open(
                file=os.path.join(self._cache_dir, self._filename),
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                self._persistant_cache.clear()
                self._persistant_cache.update(json.load(fptr))
            return HmDataOperationResult.LOAD_SUCCESS

        return await self._central.async_add_executor_job(_load)

    async def clear(self) -> None:
        """Remove stored file from disk."""

        def _clear() -> None:
            check_or_create_directory(self._cache_dir)
            if os.path.exists(os.path.join(self._cache_dir, self._filename)):
                os.unlink(os.path.join(self._cache_dir, self._filename))
            self._persistant_cache.clear()

        await self._central.async_add_executor_job(_clear)


class DeviceDescriptionCache(BasePersistentCache):
    """Cache for device/channel names."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the device description cache."""
        # {interface_id, [device_descriptions]}
        self._raw_device_descriptions: Final[dict[str, list[dict[str, Any]]]] = {}
        super().__init__(
            central=central,
            filename=FILE_DEVICES,
            persistant_cache=self._raw_device_descriptions,
        )
        # {interface_id, {device_address, [channel_address]}}
        self._addresses: Final[dict[str, dict[str, list[str]]]] = {}
        # {interface_id, {address, device_descriptions}}
        self._device_descriptions: Final[dict[str, dict[str, dict[str, Any]]]] = {}

    def _add_device_descriptions(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """Add device_descriptions to cache."""
        if interface_id not in self._raw_device_descriptions:
            self._raw_device_descriptions[interface_id] = []
        self._raw_device_descriptions[interface_id] = device_descriptions

        self._convert_device_descriptions(
            interface_id=interface_id, device_descriptions=device_descriptions
        )

    def add_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """Add device_description to cache."""
        if interface_id not in self._raw_device_descriptions:
            self._raw_device_descriptions[interface_id] = []

        if device_description not in self._raw_device_descriptions[interface_id]:
            self._raw_device_descriptions[interface_id].append(device_description)

        self._convert_device_description(
            interface_id=interface_id, device_description=device_description
        )

    def get_raw_device_descriptions(self, interface_id: str) -> list[dict[str, Any]]:
        """Find raw device in cache."""
        return self._raw_device_descriptions.get(interface_id, [])

    async def remove_device(self, device: HmDevice) -> None:
        """Remove device from cache."""
        deleted_addresses: list[str] = [device.device_address]
        deleted_addresses.extend(device.channels)
        self._add_device_descriptions(
            interface_id=device.interface_id,
            device_descriptions=[
                raw_device
                for raw_device in self.get_raw_device_descriptions(device.interface_id)
                if raw_device[HM_ADDRESS] not in deleted_addresses
            ],
        )

        for address in deleted_addresses:
            try:
                if ":" not in address and self._addresses.get(device.interface_id, {}).get(
                    address, []
                ):
                    del self._addresses[device.interface_id][address]
                if self._device_descriptions.get(device.interface_id, {}).get(address, {}):
                    del self._device_descriptions[device.interface_id][address]
            except KeyError:
                _LOGGER.warning("REMOVE_DEVICE failed: Unable to delete: %s", address)
        await self.save()

    def get_addresses(self, interface_id: str) -> dict[str, list[str]]:
        """Return the addresses by interface."""
        return self._addresses.get(interface_id, {})

    def get_channels(self, interface_id: str, device_address: str) -> dict[str, Channel]:
        """Return the device channels by interface and device_address."""
        channels: dict[str, Channel] = {}
        for channel_address in self._addresses.get(interface_id, {}).get(device_address, []):
            channel_name = str(
                self.get_device_parameter(
                    interface_id=interface_id,
                    device_address=channel_address,
                    parameter=HM_TYPE,
                )
            )
            channels[channel_address] = Channel(type=channel_name)

        return channels

    def get_device_descriptions(self, interface_id: str) -> dict[str, dict[str, Any]]:
        """Return the devices by interface."""
        return self._device_descriptions.get(interface_id, {})

    def get_device(self, interface_id: str, device_address: str) -> dict[str, Any]:
        """Return the device dict by interface and device_address."""
        return self._device_descriptions.get(interface_id, {}).get(device_address, {})

    def get_device_with_channels(self, interface_id: str, device_address: str) -> dict[str, Any]:
        """Return the device dict by interface and device_address."""
        data: dict[str, Any] = {
            device_address: self._device_descriptions.get(interface_id, {}).get(device_address, {})
        }
        children = data[device_address]["CHILDREN"]
        for channel_address in children:
            data[channel_address] = self._device_descriptions.get(interface_id, {}).get(
                channel_address, {}
            )
        return data

    def get_device_parameter(
        self, interface_id: str, device_address: str, parameter: str
    ) -> Any | None:
        """Return the device parameter by interface and device_address."""
        return (
            self._device_descriptions.get(interface_id, {}).get(device_address, {}).get(parameter)
        )

    def _convert_device_descriptions(
        self, interface_id: str, device_descriptions: list[dict[str, Any]]
    ) -> None:
        """Convert provided list of device descriptions."""
        for device_description in device_descriptions:
            self._convert_device_description(
                interface_id=interface_id, device_description=device_description
            )

    def _convert_device_description(
        self, interface_id: str, device_description: dict[str, Any]
    ) -> None:
        """Convert provided list of device descriptions."""
        if interface_id not in self._addresses:
            self._addresses[interface_id] = {}
        if interface_id not in self._device_descriptions:
            self._device_descriptions[interface_id] = {}

        address = device_description[HM_ADDRESS]
        self._device_descriptions[interface_id][address] = device_description
        if ":" not in address and address not in self._addresses[interface_id]:
            self._addresses[interface_id][address] = []
        if ":" in address:
            device_address = get_device_address(address)
            self._addresses[interface_id][device_address].append(address)

    async def load(self) -> HmDataOperationResult:
        """Load device data from disk into _device_description_cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching paramset descriptions for %s", self._central.name)
            return HmDataOperationResult.NO_LOAD
        result = await super().load()
        for (
            interface_id,
            device_descriptions,
        ) in self._raw_device_descriptions.items():
            self._convert_device_descriptions(interface_id, device_descriptions)
        return result


class ParamsetDescriptionCache(BasePersistentCache):
    """Cache for paramset descriptions."""

    def __init__(self, central: CentralUnit) -> None:
        """Init the paramset description cache."""
        # {interface_id, {channel_address, paramsets}}
        self._raw_paramset_descriptions: Final[
            dict[str, dict[str, dict[str, dict[str, Any]]]]
        ] = {}
        super().__init__(
            central=central,
            filename=FILE_PARAMSETS,
            persistant_cache=self._raw_paramset_descriptions,
        )

        # {(device_address, parameter), [channel_no]}
        self._address_parameter_cache: Final[dict[tuple[str, str], list[int]]] = {}

    def add(
        self,
        interface_id: str,
        channel_address: str,
        paramset_key: str,
        paramset_description: dict[str, Any],
    ) -> None:
        """Add paramset description to cache."""
        if interface_id not in self._raw_paramset_descriptions:
            self._raw_paramset_descriptions[interface_id] = {}
        if channel_address not in self._raw_paramset_descriptions[interface_id]:
            self._raw_paramset_descriptions[interface_id][channel_address] = {}
        if paramset_key not in self._raw_paramset_descriptions[interface_id][channel_address]:
            self._raw_paramset_descriptions[interface_id][channel_address][paramset_key] = {}

        self._raw_paramset_descriptions[interface_id][channel_address][
            paramset_key
        ] = paramset_description

    async def remove_device(self, device: HmDevice) -> None:
        """Remove device paramset descriptions from cache."""
        if interface := self._raw_paramset_descriptions.get(device.interface_id):
            for channel_address in device.channels:
                if channel_address in interface:
                    del self._raw_paramset_descriptions[device.interface_id][channel_address]
        await self.save()

    def has_interface_id(self, interface_id: str) -> bool:
        """Return if interface is in paramset_descriptions cache."""
        return interface_id in self._raw_paramset_descriptions

    def get_paramset_keys(self, interface_id: str, channel_address: str) -> list[str]:
        """Get paramset_keys from paramset descriptions cache."""
        return list(self._raw_paramset_descriptions.get(interface_id, {}).get(channel_address, []))

    def get_paramset_descriptions(
        self, interface_id: str, channel_address: str, paramset_key: str
    ) -> dict[str, Any]:
        """Get paramset descriptions from cache."""
        return (
            self._raw_paramset_descriptions.get(interface_id, {})
            .get(channel_address, {})
            .get(paramset_key, {})
        )

    def get_parameter_data(
        self, interface_id: str, channel_address: str, paramset_key: str, parameter: str
    ) -> Any:
        """Get parameter_data  from cache."""
        return (
            self._raw_paramset_descriptions.get(interface_id, {})
            .get(channel_address, {})
            .get(paramset_key, {})
            .get(parameter)
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

    def get_all_readable_parameters(self) -> list[str]:
        """Return all readable, eventing parameters from VALUES paramset."""
        parameters: set[str] = set()
        for channels in self._raw_paramset_descriptions.values():
            for channel_address in channels:
                for parameter, paramset in channels[channel_address][PARAMSET_KEY_VALUES].items():
                    operations = paramset[HM_OPERATIONS]
                    if operations & OPERATION_READ and operations & OPERATION_EVENT:
                        parameters.add(parameter)

        return sorted(parameters)

    def get_channel_addresses_by_paramset_key(
        self, interface_id: str, device_address: str
    ) -> dict[str, list[str]]:
        """Get device channel addresses."""
        channel_addresses: dict[str, list[str]] = {}
        interface_paramset_descriptions = self._raw_paramset_descriptions[interface_id]
        for (
            channel_address,
            paramset_descriptions,
        ) in interface_paramset_descriptions.items():
            if channel_address.startswith(device_address):
                for paramset_key in paramset_descriptions:
                    if paramset_key not in channel_addresses:
                        channel_addresses[paramset_key] = []
                    channel_addresses[paramset_key].append(channel_address)

        return channel_addresses

    def _init_address_parameter_list(self) -> None:
        """
        Initialize a device_address/parameter list.

        Used to identify, if a parameter name exists is in multiple channels.
        """
        for channel_paramsets in self._raw_paramset_descriptions.values():
            for channel_address, paramsets in channel_paramsets.items():
                if ":" not in channel_address:
                    continue
                device_address = get_device_address(channel_address)

                for paramset in paramsets.values():
                    if not paramset:
                        continue
                    for parameter in paramset:
                        if (
                            device_address,
                            parameter,
                        ) not in self._address_parameter_cache:
                            self._address_parameter_cache[(device_address, parameter)] = []
                        self._address_parameter_cache[(device_address, parameter)].append(
                            get_device_channel(channel_address)
                        )

    async def load(self) -> HmDataOperationResult:
        """Load paramset descriptions from disk into paramset cache."""
        if not self._central.config.use_caches:
            _LOGGER.debug("load: not caching device descriptions for %s", self._central.name)
            return HmDataOperationResult.NO_LOAD
        result = await super().load()
        self._init_address_parameter_list()
        return result

    async def save(self) -> HmDataOperationResult:
        """Save current paramset descriptions to disk."""
        result = await super().save()
        self._init_address_parameter_list()
        return result


def cleanup_cache_dirs(instance_name: str, storage_folder: str) -> None:
    """Clean up the used cached directories."""
    cache_dir = f"{storage_folder}/cache"
    files_to_delete = [FILE_DEVICES, FILE_PARAMSETS]

    def _delete_file(file_name: str) -> None:
        if os.path.exists(os.path.join(cache_dir, file_name)):
            os.unlink(os.path.join(cache_dir, file_name))

    for file_to_delete in files_to_delete:
        _delete_file(file_name=f"{instance_name}_{file_to_delete}")


@dataclass
class Channel:
    """dataclass for a device channel."""

    type: str
