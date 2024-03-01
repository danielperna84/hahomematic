"""
XML-RPC server module.

Provides the XML-RPC server which handles communication
with the CCU or Homegear.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Final
from xmlrpc.server import SimpleXMLRPCRequestHandler, SimpleXMLRPCServer

from hahomematic import central as hmcu
from hahomematic.central.decorators import callback_system_event
from hahomematic.const import IP_ANY_V4, PORT_ANY, SystemEvent
from hahomematic.support import find_free_port

_LOGGER: Final = logging.getLogger(__name__)


# pylint: disable=invalid-name
class RPCFunctions:
    """The XML-RPC functions the CCU or Homegear will expect."""

    def __init__(self, xml_rpc_server: XmlRpcServer) -> None:
        """Init RPCFunctions."""
        self._xml_rpc_server: Final = xml_rpc_server

    def event(self, interface_id: str, channel_address: str, parameter: str, value: Any) -> None:
        """If a device emits some sort event, we will handle it here."""
        if central := self._xml_rpc_server.get_central(interface_id):
            central.event(
                interface_id=interface_id,
                channel_address=channel_address,
                parameter=parameter,
                value=value,
            )

    @callback_system_event(system_event=SystemEvent.ERROR)
    def error(self, interface_id: str, error_code: str, msg: str) -> None:
        """When some error occurs the CCU / Homegear will send its error message here."""
        _LOGGER.warning(
            "ERROR failed: interface_id = %s, error_code = %i, message = %s",
            interface_id,
            int(error_code),
            str(msg),
        )

    def listDevices(self, interface_id: str) -> list[dict[str, Any]]:
        """Return already existing devices to CCU / Homegear."""
        if central := self._xml_rpc_server.get_central(interface_id):
            return central.list_devices(interface_id=interface_id)  # type: ignore[no-any-return]
        return []

    def newDevices(self, interface_id: str, device_descriptions: list[dict[str, Any]]) -> None:
        """Add new devices send from backend."""
        central: hmcu.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.create_task(
                central.add_new_devices(
                    interface_id=interface_id, device_descriptions=tuple(device_descriptions)
                ),
                name="newDevices",
            )

    def deleteDevices(self, interface_id: str, addresses: list[str]) -> None:
        """Delete devices send from backend."""
        central: hmcu.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.create_task(
                central.delete_devices(interface_id=interface_id, addresses=tuple(addresses)),
                name="deleteDevices",
            )

    @callback_system_event(system_event=SystemEvent.UPDATE_DEVICE)
    def updateDevice(self, interface_id: str, address: str, hint: int) -> None:
        """
        Update a device.

        Irrelevant, as currently only changes to link
        partners are reported.
        """
        _LOGGER.debug(
            "UPDATEDEVICE: interface_id = %s, address = %s, hint = %s",
            interface_id,
            address,
            str(hint),
        )

    @callback_system_event(system_event=SystemEvent.REPLACE_DEVICE)
    def replaceDevice(
        self, interface_id: str, old_device_address: str, new_device_address: str
    ) -> None:
        """Replace a device. Probably irrelevant for us."""
        _LOGGER.debug(
            "REPLACEDEVICE: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )

    @callback_system_event(system_event=SystemEvent.RE_ADDED_DEVICE)
    def readdedDevice(self, interface_id: str, addresses: list[str]) -> None:
        """
        Re-Add device from backend.

        Probably irrelevant for us.
        Gets called when a known devices is put into learn-mode
        while installation mode is active.
        """
        _LOGGER.debug(
            "READDEDDEVICES: interface_id = %s, addresses = %s",
            interface_id,
            str(addresses),
        )


# Restrict to specific paths.
class RequestHandler(SimpleXMLRPCRequestHandler):
    """We handle requests to / and /RPC2."""

    rpc_paths = (
        "/",
        "/RPC2",
    )


class HaHomematicXMLRPCServer(SimpleXMLRPCServer):
    """
    Simple XML-RPC server.

    Simple XML-RPC server that allows functions and a single instance
    to be installed to handle requests. The default implementation
    attempts to dispatch XML-RPC calls to the functions or instance
    installed in the server. Override the _dispatch method inherited
    from SimpleXMLRPCDispatcher to change this behavior.

    This implementation adds an additional method:
    system_listMethods(self, interface_id: str.
    """

    def system_listMethods(self, interface_id: str | None = None) -> list[str]:
        """
        Return a list of the methods supported by the server.

        system.listMethods() => ['add', 'subtract', 'multiple']
        Required for HomeMatic CCU usage.
        """
        return SimpleXMLRPCServer.system_listMethods(self)


class XmlRpcServer(threading.Thread):
    """XML-RPC server thread to handle messages from CCU / Homegear."""

    _initialized: bool = False
    _instances: Final[dict[int, XmlRpcServer]] = {}

    def __init__(
        self,
        local_port: int = PORT_ANY,
    ) -> None:
        """Init XmlRPC server."""
        if self._initialized:
            return
        self._initialized = True
        self.local_port: Final[int] = find_free_port() if local_port == PORT_ANY else local_port
        self._instances[self.local_port] = self
        threading.Thread.__init__(self, name=f"XmlRpcServer on port {self.local_port}")
        self._simple_xml_rpc_server = HaHomematicXMLRPCServer(
            (IP_ANY_V4, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
            allow_none=True,
        )
        self._simple_xml_rpc_server.register_introspection_functions()
        self._simple_xml_rpc_server.register_multicall_functions()
        self._simple_xml_rpc_server.register_instance(RPCFunctions(self), allow_dotted_names=True)
        self._centrals: Final[dict[str, hmcu.CentralUnit]] = {}

    def __new__(cls, local_port: int) -> XmlRpcServer:
        """Create new XmlRPC server."""
        if (xml_rpc := cls._instances.get(local_port)) is None:
            _LOGGER.debug("Creating XmlRpc server")
            return super().__new__(cls)
        return xml_rpc

    def run(self) -> None:
        """Run the XmlRPC-Server thread."""
        _LOGGER.debug("RUN: Starting XmlRPC-Server at http://%s:%i", IP_ANY_V4, self.local_port)
        self._simple_xml_rpc_server.serve_forever()

    def stop(self) -> None:
        """Stop the XmlRPC-Server."""
        _LOGGER.debug("STOP: Shutting down XmlRPC-Server")
        self._simple_xml_rpc_server.shutdown()
        _LOGGER.debug("STOP: Stopping XmlRPC-Server")
        self._simple_xml_rpc_server.server_close()
        _LOGGER.debug("STOP: XmlRPC-Server stopped")
        if self.local_port in self._instances:
            del self._instances[self.local_port]

    @property
    def started(self) -> bool:
        """Return if thread is active."""
        return self._started.is_set() is True  # type: ignore[attr-defined]

    def register_central(self, central: hmcu.CentralUnit) -> None:
        """Register a central in the XmlRPC-Server."""
        if not self._centrals.get(central.name):
            self._centrals[central.name] = central

    def un_register_central(self, central: hmcu.CentralUnit) -> None:
        """Unregister a central from XmlRPC-Server."""
        if self._centrals.get(central.name):
            del self._centrals[central.name]

    def get_central(self, interface_id: str) -> hmcu.CentralUnit | None:
        """Return a central by interface_id."""
        for central in self._centrals.values():
            if central.has_client(interface_id=interface_id):
                return central
        return None

    @property
    def no_central_registered(self) -> bool:
        """Return if no central is registered."""
        return len(self._centrals) == 0


def register_xml_rpc_server(local_port: int = PORT_ANY) -> XmlRpcServer:
    """Register the xml rpc server."""
    xml_rpc = XmlRpcServer(local_port=local_port)
    if not xml_rpc.started:
        xml_rpc.start()
        _LOGGER.debug("REGISTER_XML_RPC_SERVER: Starting XmlRPC-Server")
    return xml_rpc
