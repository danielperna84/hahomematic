"""
Server module.
Provides the XML-RPC server which handles communication
with the CCU or Homegear
"""
from __future__ import annotations

from datetime import datetime
import logging
import threading
from typing import Any
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    HH_EVENT_ERROR,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_RE_ADDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    HH_EVENT_UPDATE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic.decorators import callback_event, callback_system_event

_LOGGER = logging.getLogger(__name__)

_XML_RPC_SERVER: XmlRpcServer | None = None


# pylint: disable=invalid-name
class RPCFunctions:
    """
    The XML-RPC functions the CCU or Homegear will expect,
    additionally there are some internal functions for hahomematic itself.
    """

    def __init__(self, xml_rpc_server: XmlRpcServer):
        _LOGGER.debug("RPCFunctions.__init__")
        self._xml_rpc_server: XmlRpcServer = xml_rpc_server

    @callback_event
    def event(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        If a device emits some sort event, we will handle it here.
        """
        _LOGGER.debug(
            "RPCFunctions.event: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )
        central: hm_central.CentralUnit | None
        if (central := self._xml_rpc_server.get_central(interface_id)) is None:
            return
        central.last_events[interface_id] = datetime.now()
        if (channel_address, parameter) in central.entity_event_subscriptions:
            try:
                for callback in central.entity_event_subscriptions[
                    (channel_address, parameter)
                ]:
                    callback(interface_id, channel_address, parameter, value)
            except Exception:
                _LOGGER.exception(
                    "RPCFunctions.event: Failed to call callback for: %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                )

    @callback_system_event(HH_EVENT_ERROR)
    # pylint: disable=no-self-use
    def error(self, interface_id: str, error_code: str, msg: str) -> None:
        """
        When some error occurs the CCU / Homegear will send its error message here.
        """
        _LOGGER.error(
            "RPCFunctions.error: interface_id = %s, error_code = %i, message = %s",
            interface_id,
            int(error_code),
            str(msg),
        )

    @callback_system_event(HH_EVENT_LIST_DEVICES)
    def listDevices(self, interface_id: str) -> list[dict[str, Any]]:
        """
        The CCU / Homegear asks for devices known to our XML-RPC server.
        We respond to that request using this method.
        """
        central: hm_central.CentralUnit | None
        if (central := self._xml_rpc_server.get_central(interface_id)) is None:
            return []
        _LOGGER.debug("RPCFunctions.listDevices: interface_id = %s", interface_id)

        return central.raw_devices.get_device_descriptions(interface_id=interface_id)

    def newDevices(
        self, interface_id: str, dev_descriptions: list[dict[str, Any]]
    ) -> None:
        """
        The CCU / Homegear informs us about newly added devices.
        We react on that and add those devices as well.
        """

        central: hm_central.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.run_coroutine(
                central.add_new_devices(interface_id, dev_descriptions)
            )

    def deleteDevices(self, interface_id: str, addresses: list[str]) -> None:
        """
        The CCU / Homegear informs us about removed devices.
        We react on that and remove those devices as well.
        """

        central: hm_central.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.run_coroutine(central.delete_devices(interface_id, addresses))

    @callback_system_event(HH_EVENT_UPDATE_DEVICE)
    # pylint: disable=no-self-use
    def updateDevice(self, interface_id: str, address: str, hint: int) -> None:
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

    @callback_system_event(HH_EVENT_REPLACE_DEVICE)
    # pylint: disable=no-self-use
    def replaceDevice(
        self, interface_id: str, old_device_address: str, new_device_address: str
    ) -> None:
        """
        Replace a device. Probably irrelevant for us.
        """
        _LOGGER.debug(
            "RPCFunctions.replaceDevice: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )

    @callback_system_event(HH_EVENT_RE_ADDED_DEVICE)
    # pylint: disable=no-self-use
    def readdedDevice(self, interface_id: str, addresses: list[str]) -> None:
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


# Restrict to specific paths.
class RequestHandler(SimpleXMLRPCRequestHandler):
    """
    We handle requests to / and /RPC2.
    """

    rpc_paths = (
        "/",
        "/RPC2",
    )


class XmlRpcServer(threading.Thread):
    """
    XML-RPC server thread to handle messages from CCU / Homegear.
    """

    def __init__(
        self,
        local_ip: str = IP_ANY_V4,
        local_port: int = PORT_ANY,
    ):
        _LOGGER.debug("Server.__init__")
        threading.Thread.__init__(self)

        self.local_ip: str = local_ip
        self.local_port: int = local_port

        _rpc_functions = RPCFunctions(self)
        _LOGGER.debug("Server.__init__: Setting up server")
        self._simple_xml_rpc_server = SimpleXMLRPCServer(
            (self.local_ip, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
            allow_none=True,
        )

        self.local_port = self._simple_xml_rpc_server.socket.getsockname()[1]
        self._simple_xml_rpc_server.register_introspection_functions()
        self._simple_xml_rpc_server.register_multicall_functions()
        _LOGGER.debug("Server.__init__: Registering RPC functions")
        self._simple_xml_rpc_server.register_instance(
            _rpc_functions, allow_dotted_names=True
        )
        self._centrals: dict[str, hm_central.CentralUnit] = {}

    def run(self) -> None:
        """
        Run the XMLRPCServer thread.
        """
        _LOGGER.info(
            "XMLRPCServer.run: Starting XMLRPCServer at http://%s:%i",
            self.local_ip,
            self.local_port,
        )
        self._simple_xml_rpc_server.serve_forever()

    def stop(self) -> None:
        """Stops the XMLRPCServer."""
        _LOGGER.info("XMLRPCServer.stop: Shutting down XMLRPCServer")
        self._simple_xml_rpc_server.shutdown()
        _LOGGER.debug("XMLRPCServer.stop: Stopping XMLRPCServer")
        self._simple_xml_rpc_server.server_close()
        _LOGGER.info("XMLRPCServer.stop: Server XMLRPCServer")

    def register_central(self, central: hm_central.CentralUnit) -> None:
        """Register a central in the xml_rpc_server"""
        if not self._centrals.get(central.instance_name):
            self._centrals[central.instance_name] = central

    def un_register_central(self, central: hm_central.CentralUnit) -> None:
        """Unregister a central from xml_rpc_server"""
        if self._centrals.get(central.instance_name):
            del self._centrals[central.instance_name]

    def get_central(self, interface_id: str) -> hm_central.CentralUnit | None:
        """Return a central by interface_id"""
        for central in self._centrals.values():
            if central.has_client(interface_id=interface_id):
                return central
        return None

    @property
    def no_central_registered(self) -> bool:
        """Return if no central is registered."""
        return len(self._centrals) == 0


def get_xml_rpc_server() -> XmlRpcServer | None:
    """Return the XMLRPCServer."""
    return _XML_RPC_SERVER


def _set_xml_rpc_server(xml_rpc_server: XmlRpcServer | None) -> None:
    """Add a XMLRPCServer."""
    # pylint: disable=global-statement
    global _XML_RPC_SERVER
    _XML_RPC_SERVER = xml_rpc_server


def register_xml_rpc_server(
    local_ip: str = IP_ANY_V4, local_port: int = PORT_ANY
) -> XmlRpcServer:
    """Register the xml rpc server."""
    if (xml_rpc := get_xml_rpc_server()) is None:
        xml_rpc = XmlRpcServer(local_ip, local_port)
        xml_rpc.start()
        _set_xml_rpc_server(xml_rpc)
    return xml_rpc


def un_register_xml_rpc_server() -> bool:
    """Unregister the xml rpc server."""
    xml_rpc = get_xml_rpc_server()
    _LOGGER.info("XMLRPCServer.stop: Shutting down server")
    if xml_rpc and xml_rpc.no_central_registered:
        xml_rpc.stop()
        _set_xml_rpc_server(None)
        _LOGGER.info("XMLRPCServer.stop: Server stopped")
        return True

    _LOGGER.info(
        "XMLRPCServer.stop: Server NOT stopped. There is still a server instance registered."
    )
    return False
