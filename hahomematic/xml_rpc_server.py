"""
Server module.
Provides the XML-RPC server which handles communication
with the CCU or Homegear
"""
from __future__ import annotations

import logging
import threading
import time
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from hahomematic.const import (
    ATTR_HM_ADDRESS,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_ERROR,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HH_EVENT_RE_ADDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.decorators import callback_event, callback_system_event
from hahomematic.device import create_devices
import hahomematic.server as hm_server

_LOGGER = logging.getLogger(__name__)

_XML_RPC_SERVER: XMLRPCServer = None


# pylint: disable=invalid-name
class RPCFunctions:
    """
    The XML-RPC functions the CCU or Homegear will expect.
    Additionally there are some internal functions for hahomematic itself.
    """

    def __init__(self, xml_rpc_server: XMLRPCServer):
        _LOGGER.debug("RPCFunctions.__init__")
        self._xml_rpc_server: XMLRPCServer = xml_rpc_server

    @callback_event
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
        server = self._xml_rpc_server.get_server(interface_id)
        server.last_events[interface_id] = int(time.time())
        if (address, value_key) in server.entity_event_subscriptions:
            try:
                for callback in server.entity_event_subscriptions[(address, value_key)]:
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
    def listDevices(self, interface_id):
        """
        The CCU / Homegear asks for devices known to our XML-RPC server.
        We respond to that request using this method.
        """
        server = self._xml_rpc_server.get_server(interface_id)
        _LOGGER.debug("RPCFunctions.listDevices: interface_id = %s", interface_id)
        if interface_id not in server.devices_raw_cache:
            server.devices_raw_cache[interface_id] = []
        return server.devices_raw_cache[interface_id]

    @callback_system_event(HH_EVENT_NEW_DEVICES)
    def newDevices(self, interface_id, dev_descriptions):
        """
        The CCU / Homegear informs us about newly added devices.
        We react on that and add those devices as well.
        """

        async def _async_new_devices():
            """Async implementation"""
            _LOGGER.debug(
                "RPCFunctions.newDevices: interface_id = %s, dev_descriptions = %s",
                interface_id,
                len(dev_descriptions),
            )

            if interface_id not in server.devices_raw_cache:
                server.devices_raw_cache[interface_id] = []
            if interface_id not in server.devices_raw_dict:
                server.devices_raw_dict[interface_id] = {}
            if interface_id not in server.names_cache:
                server.names_cache[interface_id] = {}
            if interface_id not in server.clients:
                _LOGGER.error(
                    "RPCFunctions.newDevices: Missing client for interface_id %s.",
                    interface_id,
                )
                return True

            # We need this list to avoid adding duplicates.
            known_addresses = [
                dd[ATTR_HM_ADDRESS] for dd in server.devices_raw_cache[interface_id]
            ]
            client = server.clients[interface_id]
            for dd in dev_descriptions:
                try:
                    if dd[ATTR_HM_ADDRESS] not in known_addresses:
                        server.devices_raw_cache[interface_id].append(dd)
                        await client.fetch_paramsets(dd)
                except Exception:
                    _LOGGER.exception("RPCFunctions.newDevices: Exception")
            await server.save_devices_raw()
            await server.save_paramsets()

            hm_server.handle_device_descriptions(server, interface_id, dev_descriptions)
            await client.fetch_names()
            await server.save_names()
            create_devices(server)
            return True

        server = self._xml_rpc_server.get_server(interface_id)
        return server.run_coroutine(_async_new_devices())

    @callback_system_event(HH_EVENT_DELETE_DEVICES)
    def deleteDevices(self, interface_id, addresses):
        """
        The CCU / Homegear informs us about removed devices.
        We react on that and remove those devices as well.
        """

        async def _async_delete_devices():
            """async implementation."""
            _LOGGER.debug(
                "RPCFunctions.deleteDevices: interface_id = %s, addresses = %s",
                interface_id,
                str(addresses),
            )

            server.devices_raw_cache[interface_id] = [
                device
                for device in server.devices_raw_cache[interface_id]
                if not device[ATTR_HM_ADDRESS] in addresses
            ]
            await server.save_devices_raw()

            for address in addresses:
                try:
                    if ":" not in address:
                        del server.devices[interface_id][address]
                    del server.devices_raw_dict[interface_id][address]
                    del server.paramsets_cache[interface_id][address]
                    del server.names_cache[interface_id][address]
                    ha_device = server.hm_devices.get(address)
                    if ha_device:
                        ha_device.remove_event_subscriptions()
                        del server.hm_devices[address]
                except KeyError:
                    _LOGGER.exception("Failed to delete: %s", address)
            await server.save_paramsets()
            await server.save_names()
            return True

        server = self._xml_rpc_server.get_server(interface_id)
        return server.run_coroutine(_async_delete_devices())

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


class XMLRPCServer(threading.Thread):
    """
    XML-RPC server thread to handle messages from CCU / Homegear.
    """

    def __init__(
        self,
        local_ip=IP_ANY_V4,
        local_port=PORT_ANY,
    ):
        _LOGGER.debug("Server.__init__")
        threading.Thread.__init__(self)

        self.local_ip = local_ip
        self.local_port = int(local_port)

        rpc_functions = RPCFunctions(self)
        _LOGGER.debug("Server.__init__: Setting up server")
        self.simple_xml_rpc_server = SimpleXMLRPCServer(
            (self.local_ip, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
        )

        self.local_port = self.simple_xml_rpc_server.socket.getsockname()[1]
        self.simple_xml_rpc_server.register_introspection_functions()
        self.simple_xml_rpc_server.register_multicall_functions()
        _LOGGER.debug("Server.__init__: Registering RPC functions")
        self.simple_xml_rpc_server.register_instance(
            rpc_functions, allow_dotted_names=True
        )
        self._servers = {}

    def run(self):
        """
        Run the XMLRPCServer thread.
        """
        _LOGGER.info(
            "XMLRPCServer.run: Starting XMLRPCServer at http://%s:%i",
            self.local_ip,
            self.local_port,
        )
        self.simple_xml_rpc_server.serve_forever()

    async def stop(self):
        """Stops the XMLRPCServer."""
        _LOGGER.info("XMLRPCServer.stop: Shutting down XMLRPCServer")
        self.simple_xml_rpc_server.shutdown()
        _LOGGER.debug("XMLRPCServer.stop: Stopping XMLRPCServer")
        self.simple_xml_rpc_server.server_close()
        _LOGGER.info("XMLRPCServer.stop: Server XMLRPCServer")

    def register_server(self, server: hm_server.Server):
        """Register a server in the xml_rpc_server"""
        if not self._servers.get(server.instance_name):
            self._servers[server.instance_name] = server

    def un_register_server(self, server: hm_server.Server):
        """Unregister a server from xml_rpc_server"""
        if self._servers.get(server.instance_name):
            del self._servers[server.instance_name]

    def get_server(self, interface_id) -> hm_server.Server:
        """Return a server by interface_id"""
        for server in self._servers.values():
            client = server.clients.get(interface_id)
            if client:
                return server

    @property
    def no_server_registered(self) -> bool:
        """Return if no server is registered."""
        return len(self._servers) == 0


def get_xml_rpc_server() -> XMLRPCServer:
    """Return the XMLRPCServer."""
    return _XML_RPC_SERVER


def _set_xml_rpc_server(xml_rpc_server: XMLRPCServer) -> None:
    """Add a XMLRPCServer."""
    global _XML_RPC_SERVER
    _XML_RPC_SERVER = xml_rpc_server


def register_xml_rpc_server(local_ip=IP_ANY_V4, local_port=PORT_ANY) -> XMLRPCServer:
    """Register the xml rpc server."""
    xml_rpc = get_xml_rpc_server()
    if not xml_rpc:
        xml_rpc = XMLRPCServer(local_ip, local_port)
        xml_rpc.start()
        _set_xml_rpc_server(xml_rpc)
    return xml_rpc


def un_register_xml_rpc_server() -> bool:
    """Unregister the xml rpc server."""
    xml_rpc = get_xml_rpc_server()
    _LOGGER.info("XMLRPCServer.stop: Shutting down server")
    if xml_rpc.no_server_registered:
        xml_rpc.stop()
        _set_xml_rpc_server(None)
        _LOGGER.info("XMLRPCServer.stop: Server stopped")
        return True

    _LOGGER.info(
        "XMLRPCServer.stop: Server NOT stopped. There is still a server instance registered."
    )
    return False
