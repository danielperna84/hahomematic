"""
Server module.
Provides the XML-RPC server which handles communication
with the CCU or Homegear
"""
from __future__ import annotations

from datetime import datetime
import logging
import threading
from typing import Any, Final
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
from hahomematic.helpers import find_free_port

_LOGGER = logging.getLogger(__name__)


# pylint: disable=invalid-name
class RPCFunctions:
    """
    The XML-RPC functions the CCU or Homegear will expect,
    additionally there are some internal functions for hahomematic itself.
    """

    def __init__(self, xml_rpc_server: XmlRpcServer):
        _LOGGER.debug("__init__")
        self._xml_rpc_server: XmlRpcServer = xml_rpc_server

    @callback_event
    def event(
        self, interface_id: str, channel_address: str, parameter: str, value: Any
    ) -> None:
        """
        If a device emits some sort event, we will handle it here.
        """
        _LOGGER.debug(
            "event: interface_id = %s, channel_address = %s, parameter = %s, value = %s",
            interface_id,
            channel_address,
            parameter,
            str(value),
        )
        central: hm_central.CentralUnit | None
        if (central := self._xml_rpc_server.get_central(interface_id)) is None:
            return
        central.last_events[interface_id] = datetime.now()
        # No need to check the response of a XmlRPC-PING
        if parameter == "PONG":
            return
        if (channel_address, parameter) in central.entity_event_subscriptions:
            try:
                for callback in central.entity_event_subscriptions[
                    (channel_address, parameter)
                ]:
                    callback(interface_id, channel_address, parameter, value)
            except RuntimeError as rte:
                _LOGGER.debug(
                    "event: RuntimeError [%s]. Failed to call callback for: %s, %s, %s",
                    rte.args,
                    interface_id,
                    channel_address,
                    parameter,
                )
            except Exception as ex:
                _LOGGER.warning(
                    "event failed: Unable to call callback for: %s, %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                    ex.args,
                )

    @callback_system_event(HH_EVENT_ERROR)
    def error(self, interface_id: str, error_code: str, msg: str) -> None:
        """
        When some error occurs the CCU / Homegear will send its error message here.
        """
        _LOGGER.warning(
            "error failed: interface_id = %s, error_code = %i, message = %s",
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
        _LOGGER.debug("listDevices: interface_id = %s", interface_id)

        return central.device_descriptions.get_raw_device_descriptions(
            interface_id=interface_id
        )

    def newDevices(
        self, interface_id: str, dev_descriptions: list[dict[str, Any]]
    ) -> None:
        """
        The CCU / Homegear informs us about newly added devices.
        We react on that and add those devices as well.
        """

        central: hm_central.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.create_task(central.add_new_devices(interface_id, dev_descriptions))

    def deleteDevices(self, interface_id: str, addresses: list[str]) -> None:
        """
        The CCU / Homegear informs us about removed devices.
        We react on that and remove those devices as well.
        """

        central: hm_central.CentralUnit | None
        if central := self._xml_rpc_server.get_central(interface_id):
            central.create_task(central.delete_devices(interface_id, addresses))

    @callback_system_event(HH_EVENT_UPDATE_DEVICE)
    def updateDevice(self, interface_id: str, address: str, hint: int) -> None:
        """
        Update a device.
        Irrelevant, as currently only changes to link
        partners are reported.
        """
        _LOGGER.debug(
            "updateDevice: interface_id = %s, address = %s, hint = %s",
            interface_id,
            address,
            str(hint),
        )

    @callback_system_event(HH_EVENT_REPLACE_DEVICE)
    def replaceDevice(
        self, interface_id: str, old_device_address: str, new_device_address: str
    ) -> None:
        """
        Replace a device. Probably irrelevant for us.
        """
        _LOGGER.debug(
            "replaceDevice: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
            interface_id,
            old_device_address,
            new_device_address,
        )

    @callback_system_event(HH_EVENT_RE_ADDED_DEVICE)
    def readdedDevice(self, interface_id: str, addresses: list[str]) -> None:
        """
        Readded device. Probably irrelevant for us.
        Gets called when a known devices is put into learn-mode
        while installation mode is active.
        """
        _LOGGER.debug(
            "readdedDevices: interface_id = %s, addresses = %s",
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


class HaHomematicXMLRPCServer(SimpleXMLRPCServer):
    """Simple XML-RPC server.

    Simple XML-RPC server that allows functions and a single instance
    to be installed to handle requests. The default implementation
    attempts to dispatch XML-RPC calls to the functions or instance
    installed in the server. Override the _dispatch method inherited
    from SimpleXMLRPCDispatcher to change this behavior.

    This implementation adds an additional method (system_listMethods(self, interface_id: str).
    """

    # pylint: disable=arguments-differ
    def system_listMethods(self, interface_id: str | None = None) -> list[str]:
        """system.listMethods() => ['add', 'subtract', 'multiple']
        Returns a list of the methods supported by the server.
        Required for Homematic CCU usage."""
        return SimpleXMLRPCServer.system_listMethods(self)


class XmlRpcServer(threading.Thread):
    """
    XML-RPC server thread to handle messages from CCU / Homegear.
    """

    _initialized: bool = False
    _instances: Final[dict[int, XmlRpcServer]] = {}

    def __init__(
        self,
        local_port: int = PORT_ANY,
    ):
        """Init XmlRPC server."""
        if self._initialized:
            return
        self._initialized = True
        if local_port == PORT_ANY:
            local_port = find_free_port()
        self.local_port: int = local_port
        self._instances[self.local_port] = self
        threading.Thread.__init__(self, name=f"XmlRpcServer on port {self.local_port}")
        self._simple_xml_rpc_server = HaHomematicXMLRPCServer(
            (IP_ANY_V4, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
            allow_none=True,
        )
        _LOGGER.debug("__init__: Register functions")
        self._simple_xml_rpc_server.register_introspection_functions()
        self._simple_xml_rpc_server.register_multicall_functions()
        _LOGGER.debug("__init__: Registering RPC instance")
        self._simple_xml_rpc_server.register_instance(
            RPCFunctions(self), allow_dotted_names=True
        )
        self._centrals: Final[dict[str, hm_central.CentralUnit]] = {}

    def __new__(cls, local_port: int) -> XmlRpcServer:
        """Create new XmlRPC server."""
        if (xml_rpc := cls._instances.get(local_port)) is None:
            _LOGGER.debug("Creating XmlRpc server")
            xml_rpc = super(XmlRpcServer, cls).__new__(cls)
        return xml_rpc

    def run(self) -> None:
        """
        Run the XmlRPC-Server thread.
        """
        _LOGGER.debug(
            "run: Starting XmlRPC-Server at http://%s:%i", IP_ANY_V4, self.local_port
        )
        self._simple_xml_rpc_server.serve_forever()

    def stop(self) -> None:
        """Stops the XmlRPC-Server."""
        _LOGGER.debug("stop: Shutting down XmlRPC-Server")
        self._simple_xml_rpc_server.shutdown()
        _LOGGER.debug("stop: Stopping XmlRPC-Server")
        self._simple_xml_rpc_server.server_close()
        _LOGGER.debug("stop: XmlRPC-Server stopped")
        if self.local_port in self._instances:
            del self._instances[self.local_port]

    @property
    def started(self) -> bool:
        """return if thread is active."""
        return self._started.is_set() is True  # type: ignore[attr-defined]

    def register_central(self, central: hm_central.CentralUnit) -> None:
        """Register a central in the XmlRPC-Server"""
        if not self._centrals.get(central.name):
            self._centrals[central.name] = central

    def un_register_central(self, central: hm_central.CentralUnit) -> None:
        """Unregister a central from XmlRPC-Server"""
        if self._centrals.get(central.name):
            del self._centrals[central.name]

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


def register_xml_rpc_server(local_port: int = PORT_ANY) -> XmlRpcServer:
    """Register the xml rpc server."""
    xml_rpc = XmlRpcServer(local_port=local_port)
    if not xml_rpc.started:
        xml_rpc.start()
        _LOGGER.debug("register_xml_rpc_server: Starting XmlRPC-Server.")
    return xml_rpc
