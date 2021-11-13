# pylint: disable=broad-except,invalid-name,logging-not-lazy,line-too-long,protected-access,inconsistent-return-statements
"""
Server module.
Provides the XML-RPC server which handles communication
with the CCU or Homegear
"""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Any, Awaitable, Optional, TypeVar
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from hahomematic import config
from hahomematic.client import Client, ClientException
from hahomematic.const import (
    ATTR_HM_ADDRESS,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    DATA_NO_SAVE,
    DATA_SAVE_SUCCESS,
    DEFAULT_ENCODING,
    FILE_DEVICES,
    FILE_NAMES,
    FILE_PARAMSETS,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_ERROR,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HH_EVENT_RE_ADDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
    PRIMARY_PORTS,
)
from hahomematic.data import INSTANCES
from hahomematic.decorators import callback_event, callback_system_event
from hahomematic.device import HmDevice, create_devices
from hahomematic.entity import BaseEntity, GenericEntity

T = TypeVar("T")
_LOGGER = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
# noinspection PyPep8Naming,SpellCheckingInspection
class RPCFunctions:
    """
    The XML-RPC functions the CCU or Homegear will expect.
    Additionally there are some internal functions for hahomematic itself.
    """

    # pylint: disable=too-many-branches,too-many-statements
    def __init__(self, server):
        _LOGGER.debug("RPCFunctions.__init__")
        self._server: Server = server

    @callback_event
    # pylint: disable=no-self-use
    def event(self, interface_id, address, value_key, value):
        """
        If a device emits some sort event, we will handle it here.
        """
        _LOGGER.debug(
            "RPCFunctions.event: interface_id = %s, address = %s, value_key = %s, value = %s",
            interface_id,
            address,
            value_key,
            str(value),
        )
        self._server.last_events[interface_id] = int(time.time())
        if (address, value_key) in self._server.entity_event_subscriptions:
            try:
                for callback in self._server.entity_event_subscriptions[
                    (address, value_key)
                ]:
                    callback(interface_id, address, value_key, value)
            except Exception:
                _LOGGER.exception(
                    "RPCFunctions.event: Failed to call callback for: %s, %s, %s",
                    interface_id,
                    address,
                    value_key,
                )

        return True

    @callback_system_event(HH_EVENT_ERROR)
    # pylint: disable=no-self-use
    def error(self, interface_id, error_code, msg):
        """
        When some error occurs the CCU / Homegear will send it's error message here.
        """
        _LOGGER.error(
            "RPCFunctions.error: interface_id = %s, error_code = %i, message = %s",
            interface_id,
            int(error_code),
            str(msg),
        )
        return True

    @callback_system_event(HH_EVENT_LIST_DEVICES)
    # pylint: disable=no-self-use
    def listDevices(self, interface_id):
        """
        The CCU / Homegear asks for devices known to our XML-RPC server.
        We respond to that request using this method.
        """
        _LOGGER.debug("RPCFunctions.listDevices: interface_id = %s", interface_id)
        if interface_id not in self._server.devices_raw_cache:
            self._server.devices_raw_cache[interface_id] = []
        return self._server.devices_raw_cache[interface_id]

    @callback_system_event(HH_EVENT_NEW_DEVICES)
    # pylint: disable=no-self-use
    def newDevices(self, interface_id, dev_descriptions):
        async def _async_newDevices():
            """
            The CCU / Homegear informs us about newly added devices.
            We react on that and add those devices as well.
            """
            _LOGGER.debug(
                "RPCFunctions.newDevices: interface_id = %s, dev_descriptions = %s",
                interface_id,
                len(dev_descriptions),
            )

            if interface_id not in self._server.devices_raw_cache:
                self._server.devices_raw_cache[interface_id] = []
            if interface_id not in self._server.devices_raw_dict:
                self._server.devices_raw_dict[interface_id] = {}
            if interface_id not in self._server.names_cache:
                self._server.names_cache[interface_id] = {}
            if interface_id not in self._server.clients:
                _LOGGER.error(
                    "RPCFunctions.newDevices: Missing client for interface_id %s.",
                    interface_id,
                )
                return True

            # We need this list to avoid adding duplicates.
            known_addresses = [
                dd[ATTR_HM_ADDRESS]
                for dd in self._server.devices_raw_cache[interface_id]
            ]
            client = self._server.clients[interface_id]
            for dd in dev_descriptions:
                try:
                    if dd[ATTR_HM_ADDRESS] not in known_addresses:
                        self._server.devices_raw_cache[interface_id].append(dd)
                        await client.fetch_paramsets(dd)
                except Exception:
                    _LOGGER.exception("RPCFunctions.newDevices: Exception")
            await self._server.save_devices_raw()
            await self._server.save_paramsets()

            handle_device_descriptions(self._server, interface_id, dev_descriptions)
            await client.fetch_names()
            await self._server.save_names()
            create_devices(self._server)
            return True

        return self._server.run_coroutine(_async_newDevices())

    @callback_system_event(HH_EVENT_DELETE_DEVICES)
    # pylint: disable=no-self-use
    def deleteDevices(self, interface_id, addresses):
        async def _async_deleteDevices():
            """
            The CCU / Homegear informs us about removed devices.
            We react on that and remove those devices as well.
            """
            _LOGGER.debug(
                "RPCFunctions.deleteDevices: interface_id = %s, addresses = %s",
                interface_id,
                str(addresses),
            )

            self._server.devices_raw_cache[interface_id] = [
                device
                for device in self._server.devices_raw_cache[interface_id]
                if not device[ATTR_HM_ADDRESS] in addresses
            ]
            await self._server.save_devices_raw()

            for address in addresses:
                try:
                    if ":" not in address:
                        del self._server.devices[interface_id][address]
                    del self._server.devices_raw_dict[interface_id][address]
                    del self._server.paramsets_cache[interface_id][address]
                    del self._server.names_cache[interface_id][address]
                    ha_device = self._server.hm_devices.get(address)
                    if ha_device:
                        ha_device.remove_event_subscriptions()
                        del self._server.hm_devices[address]
                except KeyError:
                    _LOGGER.exception("Failed to delete: %s", address)
            await self._server.save_paramsets()
            await self._server.save_names()
            return True

        return self._server.run_coroutine(_async_deleteDevices())

    @callback_system_event(HH_EVENT_UPDATE_DEVICE)
    # pylint: disable=no-self-use
    def updateDevice(self, interface_id, address, hint):
        """
        Update a device.
        Irrelevant, as currently only changes to link
        partners are reported.
        """
        _LOGGER.debug(
            "RPCFunctions.updateDevice: interface_id = %s, address = %s, hint = %s",
            interface_id,
            address,
            str(hint),
        )
        return True

    @callback_system_event(HH_EVENT_REPLACE_DEVICE)
    # pylint: disable=no-self-use
    def replaceDevice(self, interface_id, old_device_address, new_device_address):
        """
        Replace a device. Probably irrelevant for us.
        """
        _LOGGER.debug(
            "RPCFunctions.replaceDevice: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )
        return True

    @callback_system_event(HH_EVENT_RE_ADDED_DEVICE)
    # pylint: disable=no-self-use
    def readdedDevice(self, interface_id, addresses):
        """
        Readded device. Probably irrelevant for us.
        Gets called when a known devices is put into learn-mode
        while installation mode is active.
        """
        _LOGGER.debug(
            "RPCFunctions.readdedDevices: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )
        return True


# Restrict to specific paths.
class RequestHandler(SimpleXMLRPCRequestHandler):
    """
    We handle requests to / and /RPC2.
    """

    rpc_paths = (
        "/",
        "/RPC2",
    )


# pylint: disable=too-many-public-methods
class Server(threading.Thread):
    """
    XML-RPC server thread to handle messages from CCU / Homegear.
    """

    def __init__(
        self,
        instance_name,
        entry_id,
        loop,
        local_ip=IP_ANY_V4,
        local_port=PORT_ANY,
        enable_virtual_channels=False,
    ):
        _LOGGER.debug("Server.__init__")
        threading.Thread.__init__(self)

        self.instance_name = instance_name
        self.entry_id = entry_id
        self.local_ip = local_ip
        self.local_port = int(local_port)
        self._loop = loop
        self.enable_virtual_channels = enable_virtual_channels
        # Caches for CCU data
        # {interface_id, {address, paramsets}}
        self.paramsets_cache = {}
        # {interface_id,  {address, name}}
        self.names_cache = {}
        # {interface_id, {counter, device}}
        self.devices_raw_cache = {}
        # {interface_id, client}
        self.clients: dict[str, Client] = {}
        # {url, client}
        self.clients_by_init_url: dict[str, Client] = {}
        # {interface_id, {address, channel_address}}
        self.devices = {}
        # {interface_id, {address, dev_descriptions}
        self.devices_raw_dict = {}
        # {{channel_address, parameter}, event_handle}
        self.entity_event_subscriptions: dict[tuple[str, str], Any] = {}
        # {unique_id, entity}
        self.hm_entities: dict[str, BaseEntity] = {}
        # {device_address, device}
        self.hm_devices: dict[str, HmDevice] = {}

        self.last_events = {}

        # Signature: f(name, *args)
        self.callback_system_event = None
        # Signature: f(interface_id, address, value_key, value)
        self.callback_entity_event = None
        # Signature: f(interface_id, address, value_key, value)
        self.callback_click_event = None
        # Signature: f(interface_id, address, value_key, value)
        self.callback_impulse_event = None

        INSTANCES[instance_name] = self
        self._init_xml_rpc_server()
        self._load_caches()
        self._connection_checker = ConnectionChecker(self)

    @property
    def loop(self):
        if not self._loop:
            self._loop = asyncio.get_running_loop()
        return self._loop

    def _init_xml_rpc_server(self):
        """Setup server to handle requests from CCU / Homegear."""
        self._rpc_functions = RPCFunctions(self)
        _LOGGER.debug("Server.__init__: Setting up server")
        self.xml_rpc_server = SimpleXMLRPCServer(
            (self.local_ip, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
        )
        self.local_port = self.xml_rpc_server.socket.getsockname()[1]
        self.xml_rpc_server.register_introspection_functions()
        self.xml_rpc_server.register_multicall_functions()
        _LOGGER.debug("Server.__init__: Registering RPC functions")
        self.xml_rpc_server.register_instance(
            self._rpc_functions, allow_dotted_names=True
        )

    def _load_caches(self):
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

    def run(self):
        """
        Run the server thread.
        """
        _LOGGER.info(
            "Server.run: Creating entities and starting server at http://%s:%i",
            self.local_ip,
            self.local_port,
        )
        if not self.clients:
            raise Exception("No clients initialized. Not starting server.")
        try:
            create_devices(self)
        except Exception as err:
            _LOGGER.exception("Server.run: Failed to create entities")
            raise Exception("entity-creation-error") from err
        self.xml_rpc_server.serve_forever()

    async def stop(self):
        """
        To stop the server we de-init from the CCU / Homegear,
        then shut down our XML-RPC server.
        """
        _LOGGER.info("Server.stop: Stop connection checker.")
        await self.stop_connection_checker()
        for name, client in self.clients.items():
            if await client.proxy_de_init():
                _LOGGER.info("Server.stop: Proxy de-initialized: %s", name)
            client.stop()

        _LOGGER.info("Server.stop: Clearing existing clients. Please recreate them!")
        self.clients.clear()
        self.clients_by_init_url.clear()
        _LOGGER.info("Server.stop: Shutting down server")
        self.xml_rpc_server.shutdown()
        _LOGGER.debug("Server.stop: Stopping Server")
        self.xml_rpc_server.server_close()
        _LOGGER.info("Server.stop: Server stopped")
        _LOGGER.debug("Server.stop: Removing instance")
        del INSTANCES[self.instance_name]

    def create_task(self, target: Awaitable) -> None:
        """Add task to the executor pool."""
        self.loop.call_soon_threadsafe(self.async_create_task, target)

    def async_create_task(self, target: Awaitable) -> asyncio.Task:
        """Create a task from within the event loop. This method must be run in the event loop."""
        return self.loop.create_task(target)

    def run_coroutine(self, coro):
        """call coroutine from sync"""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()

    async def async_add_executor_job(self, fn, *args) -> Awaitable[T]:
        """Add an executor job from within the event loop."""
        return await self.loop.run_in_executor(None, fn, *args)

    def start_connection_checker(self):
        """Start the connection checker."""
        self._connection_checker.start()

    async def stop_connection_checker(self):
        """Start the connection checker."""
        self._connection_checker.stop()

    async def is_connected(self) -> bool:
        """Check connection to ccu."""
        for client in self.clients.values():
            if not await client.is_connected():
                _LOGGER.warning(
                    "Server.is_connected: No connection to %s.", client.name
                )
                return False
        return True

    async def reconnect(self):
        """re-init all RPC clients."""
        if await self.is_connected():
            _LOGGER.warning(
                "Server.reconnect: re-connect to server %s",
                self.instance_name,
            )
            for client in self.clients.values():
                await client.proxy_re_init()

    async def get_all_system_variables(self):
        """Get all system variables from CCU / Homegear."""
        return await self._get_client().get_all_system_variables()

    async def get_system_variable(self, name):
        """Get single system variable from CCU / Homegear."""
        return await self._get_client().get_system_variable(name)

    async def set_system_variable(self, name, value):
        """Set a system variable on CCU / Homegear."""
        await self._get_client().set_system_variable(name, value)

    async def get_service_messages(self):
        """Get service messages from CCU / Homegear."""
        await self._get_client().get_service_messages()

    # pylint: disable=too-many-arguments
    async def set_install_mode(
        self, interface_id, on=True, t=60, mode=1, address=None
    ) -> None:
        """Activate or deactivate install-mode on CCU / Homegear."""
        await self._get_client(interface_id).set_install_mode(
            on=on, t=t, mode=mode, address=address
        )

    async def get_install_mode(self, interface_id) -> int:
        """Get remaining time in seconds install mode is active from CCU / Homegear."""
        return await self._get_client(interface_id).get_install_mode()

    # pylint: disable=too-many-arguments
    async def put_paramset(self, interface_id, address, paramset, value, rx_mode=None):
        """Set paramsets manually."""
        await self._get_client(interface_id).put_paramset(
            address=address, paramset=paramset, value=value, rx_mode=rx_mode
        )

    def get_hm_entities_by_platform(self, platform):
        """
        Return all hm-entities by platform
        """
        hm_entities = []
        for entity in self.hm_entities.values():
            if entity and entity.platform == platform and entity.create_in_ha:
                hm_entities.append(entity)

        return hm_entities

    def _get_client(self, interface_id=None) -> Client:
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
            raise ClientException(message, err)

    def get_hm_entity_by_parameter(self, address, parameter) -> Optional[GenericEntity]:
        """Get entity by address and parameter."""
        if ":" in address:
            device_address = address.split(":")[0]
            device = self.hm_devices.get(device_address)
            if device:
                entity = device.entities.get((address, parameter))
                if entity:
                    return entity
        return None

    def has_address(self, address):
        """Check if address is handled by server."""
        device_address = address
        if ":" in address:
            device_address = device_address.split(":")[0]

        return self.hm_devices.get(device_address) is not None

    def get_all_parameters(self):
        """Return all parameters"""
        parameters = set()
        for interface_id in self.paramsets_cache:
            for address in self.paramsets_cache[interface_id]:
                for paramset in self.paramsets_cache[interface_id][address].values():
                    parameters.update(paramset)

        return sorted(parameters)

    def get_parameters(self, address):
        """Return all parameters of a device"""
        parameters = set()
        for interface_id in self.paramsets_cache:
            for p_address in self.paramsets_cache[interface_id]:
                if p_address.startswith(address):
                    for paramset in self.paramsets_cache[interface_id][
                        p_address
                    ].values():
                        parameters.update(paramset)

        return sorted(parameters)

    def get_all_used_parameters(self):
        """Return used parameters"""
        parameters = set()
        for entity in self.hm_entities.values():
            if isinstance(entity, GenericEntity):
                parameter = getattr(entity, "parameter", None)
                if parameter:
                    parameters.add(entity.parameter)

        return sorted(parameters)

    def get_used_parameters(self, address):
        """Return used parameters"""
        parameters = set()
        device = self.hm_devices.get(address)
        if device:
            for entity in device.entities.values():
                parameter = getattr(entity, "parameter", None)
                if parameter:
                    parameters.add(entity.parameter)

        return sorted(parameters)

    async def save_devices_raw(self):
        """
        Save current device data in DEVICES_RAW to disk.
        """

        def _save_devices_raw():
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

    def load_devices_raw(self):
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

    def clear_devices_raw(self):
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

    async def save_paramsets(self):
        """
        Save current paramset data in PARAMSETS to disk.
        """

        def _save_paramsets():
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

        return await self.async_add_executor_job(_save_paramsets)

    def load_paramsets(self):
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

    def clear_paramsets(self):
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

    async def save_names(self):
        """
        Save current name data in NAMES to disk.
        """

        def _save_names():
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

    def load_names(self):
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

    def clear_names(self):
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

    def clear_all(self):
        """
        Clear all stored data.
        """
        self.clear_devices_raw()
        self.clear_paramsets()
        self.clear_names()


# pylint: disable=too-many-public-methods
class ConnectionChecker(threading.Thread):
    """
    Periodically check Connection to CCU / Homegear.
    """

    def __init__(self, server: Server):
        threading.Thread.__init__(self)
        self._server = server
        self._active = True

    def run(self):
        """
        Run the server thread.
        """
        _LOGGER.info(
            "ConnectionCecker.run: Init connection checker to server %s",
            self._server.instance_name,
        )

        self._server.run_coroutine(self._check_connection())

    def stop(self):
        """
        To stop the ConnectionChecker.
        """
        self._active = False

    async def _check_connection(self):
        while self._active:
            _LOGGER.debug(
                "ConnectionCecker.check_connection: Checking connection to server %s",
                self._server.instance_name,
            )
            if not await self._server.is_connected():
                _LOGGER.warning(
                    "ConnectionCecker.check_connection: No connection to server %s",
                    self._server.instance_name,
                )
                await asyncio.sleep(config.CONNECTION_CHECKER_INTERVAL.seconds)
                await self._server.reconnect()
            await asyncio.sleep(config.CONNECTION_CHECKER_INTERVAL.seconds)


def handle_device_descriptions(server, interface_id, dev_descriptions):
    """
    Handle provided list of device descriptions.
    """
    if interface_id not in server.devices:
        server.devices[interface_id] = {}
    if interface_id not in server.devices_raw_dict:
        server.devices_raw_dict[interface_id] = {}
    for dd in dev_descriptions:
        address = dd[ATTR_HM_ADDRESS]
        server.devices_raw_dict[interface_id][address] = dd
        if ":" not in address and address not in server.devices[interface_id]:
            server.devices[interface_id][address] = {}
        if ":" in address:
            main, _ = address.split(":")
            if main not in server.devices[interface_id]:
                server.devices[interface_id][main] = {}
            server.devices[interface_id][main][address] = {}


def check_cache_dir():
    """Check presence of cache directory."""
    if config.CACHE_DIR is None:
        return False
    if not os.path.exists(config.CACHE_DIR):
        os.makedirs(config.CACHE_DIR)
    return True
