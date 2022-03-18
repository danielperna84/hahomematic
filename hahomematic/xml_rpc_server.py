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
                    "event: Failed to call callback for: %s, %s, %s, %s",
                    interface_id,
                    channel_address,
                    parameter,
                    ex.args,
                )

    @callback_system_event(HH_EVENT_ERROR)
    # pylint: disable=no-self-use
    def error(self, interface_id: str, error_code: str, msg: str) -> None:
        """
        When some error occurs the CCU / Homegear will send its error message here.
        """
        _LOGGER.warning(
            "error: interface_id = %s, error_code = %i, message = %s",
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
    # pylint: disable=no-self-use
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
    # pylint: disable=no-self-use
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
    # pylint: disable=no-self-use
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

    def __init__(
        self,
        local_ip: str = IP_ANY_V4,
        local_port: int = PORT_ANY,
    ):
        _LOGGER.debug("__init__")
        threading.Thread.__init__(self)

        self.local_ip: str = local_ip
        self.local_port: int = local_port

        _rpc_functions = RPCFunctions(self)
        _LOGGER.debug("__init__: Setting up server")
        self._simple_xml_rpc_server = HaHomematicXMLRPCServer(
            (self.local_ip, self.local_port),
            requestHandler=RequestHandler,
            logRequests=False,
            allow_none=True,
        )

        self.local_port = self._simple_xml_rpc_server.socket.getsockname()[1]
        self._simple_xml_rpc_server.register_introspection_functions()
        self._simple_xml_rpc_server.register_multicall_functions()
        _LOGGER.debug("__init__: Registering RPC functions")
        self._simple_xml_rpc_server.register_instance(
            _rpc_functions, allow_dotted_names=True
        )
        self._centrals: dict[str, hm_central.CentralUnit] = {}

    def run(self) -> None:
        """
        Run the XmlRPC-Server thread.
        """
        _LOGGER.info(
            "run: Starting XmlRPC-Server at http://%s:%i",
            self.local_ip,
            self.local_port,
        )
        self._simple_xml_rpc_server.serve_forever()

    def stop(self) -> None:
        """Stops the XmlRPC-Server."""
        _LOGGER.info("stop: Shutting down XmlRPC-Server")
        self._simple_xml_rpc_server.shutdown()
        _LOGGER.debug("stop: Stopping XmlRPC-Server")
        self._simple_xml_rpc_server.server_close()
        _LOGGER.info("stop: Server XmlRPC-Server")

    def register_central(self, central: hm_central.CentralUnit) -> None:
        """Register a central in the XmlRPC-Server"""
        if not self._centrals.get(central.instance_name):
            self._centrals[central.instance_name] = central

    def un_register_central(self, central: hm_central.CentralUnit) -> None:
        """Unregister a central from XmlRPC-Server"""
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
    """Return the XmlRPC-Server."""
    return _XML_RPC_SERVER


def _set_xml_rpc_server(xml_rpc_server: XmlRpcServer | None) -> None:
    """Add a XmlRPC-Server."""
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
        _LOGGER.info("register_xml_rpc_server: Registering XmlRPC-Server.")
        _set_xml_rpc_server(xml_rpc)
    return xml_rpc


def un_register_xml_rpc_server() -> bool:
    """Unregister the xml rpc server."""
    xml_rpc = get_xml_rpc_server()
    _LOGGER.info("stop: Trying to shut down XmlRPC-Server")
    if xml_rpc and xml_rpc.no_central_registered:
        xml_rpc.stop()
        _set_xml_rpc_server(None)
        _LOGGER.info("stop: XmlRPC-Server stopped")
        return True

    _LOGGER.info(
        "stop: shared XmlRPC-Server NOT stopped. There is still another central instance registered."
    )
    return False
