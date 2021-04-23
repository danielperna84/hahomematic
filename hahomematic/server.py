# pylint: disable=broad-except,invalid-name,logging-not-lazy,line-too-long,protected-access,inconsistent-return-statements
"""
Server module.
Provides the XML-RPC server which handles communication
with the CCU or Homegear
"""

import os
import time
import json
import logging
import threading
from xmlrpc.server import SimpleXMLRPCServer
from xmlrpc.server import SimpleXMLRPCRequestHandler

from hahomematic.const import (
    ATTR_HM_ADDRESS,
    BACKEND_CCU,
    BACKEND_HOMEGEAR,
    FILE_DEVICES,
    FILE_PARAMSETS,
    FILE_NAMES,
    HH_EVENT_DELETE_DEVICES,
    HH_EVENT_DEVICES_CREATED,
    HH_EVENT_ERROR,
    HH_EVENT_LIST_DEVICES,
    HH_EVENT_NEW_DEVICES,
    HH_EVENT_UPDATE_DEVICE,
    HH_EVENT_READDED_DEVICE,
    HH_EVENT_REPLACE_DEVICE,
    IP_ANY_V4,
    PORT_ANY,
)
from hahomematic import data, config
from hahomematic.decorators import systemcallback, eventcallback
from hahomematic.device import Device

LOG = logging.getLogger(__name__)

# pylint: disable=too-many-instance-attributes
class RPCFunctions():
    """
    The XML-RPC functions the CCU or Homegear will expect.
    Additionally there are some internal functions for hahomematic itself.
    """
    # pylint: disable=too-many-branches,too-many-statements
    def __init__(self):
        LOG.debug("RPCFunctions.__init__")

    @eventcallback
    # pylint: disable=no-self-use
    def event(self, interface_id, address, value_key, value):
        """
        If a device emits some sort event, we will handle it here.
        """
        LOG.debug("RPCFunctions.event: interface_id = %s, address = %s, value_key = %s, value = %s",
                  interface_id, address, value_key, str(value))
        data.SERVER.last_events[interface_id] = int(time.time())
        if (address, value_key) in data.EVENT_SUBSCRIPTIONS:
            try:
                for callback in data.EVENT_SUBSCRIPTIONS[(address, value_key)]:
                    callback(interface_id, address, value_key, value)
            except Exception:
                LOG.exception("RPCFunctions.event: Failed to call callback for: %s, %s, %s",
                              interface_id, address, value_key)
        if ':' in address:
            device_address = address.split(':')[0]
            if device_address in data.EVENT_SUBSCRIPTIONS_DEVICE:
                try:
                    for callback in data.EVENT_SUBSCRIPTIONS_DEVICE[device_address]:
                        callback(interface_id, address, value_key, value)
                except Exception:
                    LOG.exception("RPCFunctions.event: Failed to call device-callback for: %s, %s, %s",
                                    interface_id, address, value_key)
        return True

    @systemcallback(HH_EVENT_ERROR)
    # pylint: disable=no-self-use
    def error(self, interface_id, errorcode, msg):
        """
        When some error occurs the CCU / Homegear will send it's error message here.
        """
        LOG.error("RPCFunctions.error: interface_id = %s, errorcode = %i, message = %s",
                  interface_id, int(errorcode), str(msg))
        return True

    @systemcallback(HH_EVENT_LIST_DEVICES)
    # pylint: disable=no-self-use
    def listDevices(self, interface_id):
        """
        The CCU / Homegear asks for devices known to our XML-RPC server.
        We respond to that request using this method.
        """
        LOG.debug("RPCFunctions.listDevices: interface_id = %s", interface_id)
        if interface_id not in data.DEVICES_RAW:
            data.DEVICES_RAW[interface_id] = []
        return data.DEVICES_RAW[interface_id]

    @systemcallback(HH_EVENT_NEW_DEVICES)
    # pylint: disable=no-self-use
    def newDevices(self, interface_id, dev_descriptions):
        """
        The CCU / Homegear informs us about newly added devices.
        We react on that and add those devices as well.
        """
        LOG.debug("RPCFunctions.newDevices: interface_id = %s, dev_descriptions = %s",
                  interface_id, len(dev_descriptions))
        if interface_id not in data.DEVICES_RAW:
            data.DEVICES_RAW[interface_id] = []
        if interface_id not in data.DEVICES_RAW_DICT:
            data.DEVICES_RAW_DICT[interface_id] = {}
        if interface_id not in data.NAMES:
            data.NAMES[interface_id] = {}
        if interface_id not in data.CLIENTS:
            LOG.error("RPCFunctions.newDevices: Missing client for interface_id %s.",
                      interface_id)
            return True
        client = data.CLIENTS[interface_id]

        # We need this list to avoid adding duplicates.
        known_addresses = [dd[ATTR_HM_ADDRESS] for dd in data.DEVICES_RAW[interface_id]]
        for dd in dev_descriptions:
            try:
                if dd[ATTR_HM_ADDRESS] not in known_addresses:
                    data.DEVICES_RAW[interface_id].append(dd)
                    client.fetch_paramsets(dd)
            except Exception:
                LOG.exception("RPCFunctions.newDevices: Exception")
        save_devices_raw()
        save_paramsets()

        handle_device_descriptions(interface_id, dev_descriptions)
        if client.backend == BACKEND_CCU:
            client.fetch_names_json()
        elif client.backend == BACKEND_HOMEGEAR:
            client.fetch_names_metadata()
        save_names()
        create_devices()
        return True

    @systemcallback(HH_EVENT_DELETE_DEVICES)
    # pylint: disable=no-self-use
    def deleteDevices(self, interface_id, addresses):
        """
        The CCU / Homegear informs us about removed devices.
        We react on that and remove those devices as well.
        """
        LOG.debug("RPCFunctions.deleteDevices: interface_id = %s, addresses = %s",
                  interface_id, str(addresses))
        data.DEVICES_RAW[interface_id] = [device for device in data.DEVICES_RAW[
            interface_id] if not device[ATTR_HM_ADDRESS] in addresses]
        save_devices_raw()
        for address in addresses:
            try:
                if ':' not in address:
                    del data.DEVICES[interface_id][address]
                del data.DEVICES_RAW_DICT[interface_id][address]
                del data.PARAMSETS[interface_id][address]
            except KeyError:
                LOG.exception("Failed to delete: %s", address)
        save_paramsets()
        return True

    @systemcallback(HH_EVENT_UPDATE_DEVICE)
    # pylint: disable=no-self-use
    def updateDevice(self, interface_id, address, hint):
        """
        Update a device.
        Irrelevant, as currently only changes to link
        partners are reported.
        """
        LOG.debug("RPCFunctions.updateDevice: interface_id = %s, address = %s, hint = %s",
                  interface_id, address, str(hint))
        return True

    @systemcallback(HH_EVENT_REPLACE_DEVICE)
    # pylint: disable=no-self-use
    def replaceDevice(self, interface_id, oldDeviceAddress, newDeviceAddress):
        """
        Replace a device. Probably irrelevant for us.
        """
        LOG.debug("RPCFunctions.replaceDevice: interface_id = %s, oldDeviceAddress = %s, newDeviceAddress = %s",
                  interface_id, oldDeviceAddress, newDeviceAddress)
        return True

    @systemcallback(HH_EVENT_READDED_DEVICE)
    # pylint: disable=no-self-use
    def readdedDevice(self, interface_id, addresses):
        """
        Readded device. Probably irrelevant for us.
        Gets called when a known devices is put into learn-mode
        while installation mode is active.
        """
        LOG.debug("RPCFunctions.readdedDevices: interface_id = %s, addresses = %s",
                  interface_id, str(addresses))
        return True

# Restrict to specific paths.
class RequestHandler(SimpleXMLRPCRequestHandler):
    """
    We handle requests to / and /RPC2.
    """
    rpc_paths = ('/', '/RPC2',)

class Server(threading.Thread):
    """
    XML-RPC server thread to handle messages from CCU / Homegear.
    """
    def __init__(self, local_ip=IP_ANY_V4, local_port=PORT_ANY):
        LOG.debug("Server.__init__")
        threading.Thread.__init__(self)

        self.local_ip = local_ip
        self.local_port = int(local_port)

        self._rpcfunctions = RPCFunctions()

        self.last_events = {}

        # Setup server to handle requests from CCU / Homegear
        LOG.debug("Server.__init__: Setting up server")
        self.server = SimpleXMLRPCServer((self.local_ip, self.local_port),
                                         requestHandler=RequestHandler,
                                         logRequests=False)
        self.local_port = self.server.socket.getsockname()[1]
        self.server.register_introspection_functions()
        self.server.register_multicall_functions()
        LOG.debug("Server.__init__: Registering RPC functions")
        self.server.register_instance(self._rpcfunctions, allow_dotted_names=True)
        data.SERVER = self
        load_devices_raw()
        load_paramsets()
        load_names()
        for interface_id, device_descriptions in data.DEVICES_RAW.items():
            if interface_id not in data.PARAMSETS:
                data.PARAMSETS[interface_id] = {}
            handle_device_descriptions(interface_id, device_descriptions)

    def run(self):
        """
        Run the server thread.
        """
        LOG.info("Server.run: Creating entities and starting server at http://%s:%i",
                 self.local_ip, self.local_port)
        if not data.CLIENTS:
            raise Exception("No clients initialized. Not starting server.")
        try:
            create_devices()
        except Exception as err:
            LOG.exception("Server.run: Failed to create entities")
            raise Exception("entitiy-creation-error") from err
        self.server.serve_forever()

    def stop(self):
        """
        To stop the server we de-init from the CCU / Homegear,
        then shut down our XML-RPC server.
        """
        for name, client in data.CLIENTS.items():
            if client.proxy_de_init():
                LOG.info("Server.stop: Proxy de-initialized: %s", name)
        LOG.info("Server.stop: Clearing existing clients. Please recreate them!")
        data.CLIENTS.clear()
        data.CLIENTS_BY_INIT_URL.clear()
        LOG.info("Server.stop: Shutting down server")
        self.server.shutdown()
        LOG.debug("Server.stop: Stopping Server")
        self.server.server_close()
        LOG.info("Server.stop: Server stopped")
        LOG.debug("Server.stop: Setting data.SERVER to None")
        data.SERVER = None

def handle_device_descriptions(interface_id, dev_descriptions):
    """
    Handle provided list of device descriptions.
    """
    if interface_id not in data.DEVICES:
        data.DEVICES[interface_id] = {}
    if interface_id not in data.DEVICES_RAW_DICT:
        data.DEVICES_RAW_DICT[interface_id] = {}
    for dd in dev_descriptions:
        address = dd[ATTR_HM_ADDRESS]
        data.DEVICES_RAW_DICT[interface_id][address] = dd
        if ':' not in address and address not in data.DEVICES[interface_id]:
            data.DEVICES[interface_id][address] = {}
        if ':' in address:
            main, _ = address.split(':')
            if main not in data.DEVICES[interface_id]:
                data.DEVICES[interface_id][main] = {}
            data.DEVICES[interface_id][main][address] = {}

def create_devices():
    """
    Trigger createion of the objects that expose the functionality.
    """
    new_devices = set()
    new_entities = set()
    for interface_id in data.DEVICES:
        if interface_id not in data.CLIENTS:
            LOG.warning("create_devices: Skipping interface %s, missing client.", interface_id)
            continue
        if interface_id not in data.PARAMSETS:
            LOG.warning("create_devices: Skipping interface %s, missing paramsets.", interface_id)
            continue
        for device_address in data.DEVICES[interface_id]:
            # Do we check for duplicates here? For now we do.
            if device_address in data.HA_DEVICES:
                LOG.warning("create_devices: Skipping device %s on %s, already exists.",
                            device_address, interface_id)
                continue
            try:
                data.HA_DEVICES[device_address] = Device(interface_id, device_address)
                new_devices.add(device_address)
            except Exception:
                LOG.exception("create_devices: Failed to create device: %s, %s",
                              interface_id, device_address)
            try:
                new_entities.update(data.HA_DEVICES[device_address].create_entities())
            except Exception:
                LOG.exception("create_devices: Failed to create entities: %s, %s",
                              interface_id, device_address)
    if callable(config.CALLBACK_SYSTEM):
        # pylint: disable=not-callable
        config.CALLBACK_SYSTEM(HH_EVENT_DEVICES_CREATED, new_devices, new_entities)

def check_cache_dir():
    """Check presence of cache directory."""
    if config.CACHE_DIR is None:
        return False
    if not os.path.exists(config.CACHE_DIR):
        os.makedirs(config.CACHE_DIR)
    return True

def save_devices_raw():
    """
    Save current device data in DEVICES_RAW to disk.
    """
    if not check_cache_dir():
        return
    with open(os.path.join(config.CACHE_DIR, FILE_DEVICES), 'w') as fptr:
        json.dump(data.DEVICES_RAW, fptr)

def load_devices_raw():
    """
    Load device data from disk into DEVICES_RAW.
    """
    if not check_cache_dir():
        return
    if not os.path.exists(os.path.join(config.CACHE_DIR, FILE_DEVICES)):
        return
    with open(os.path.join(config.CACHE_DIR, FILE_DEVICES)) as fptr:
        data.DEVICES_RAW = json.load(fptr)

def clear_devices_raw():
    """
    Remove stored device data from disk and clear DEVICES_RAW.
    """
    check_cache_dir()
    if os.path.exists(os.path.join(config.CACHE_DIR, FILE_DEVICES)):
        os.unlink(os.path.join(config.CACHE_DIR, FILE_DEVICES))
    data.DEVICES_RAW.clear()

def save_paramsets():
    """
    Save current paramset data in PARAMSETS to disk.
    """
    if not check_cache_dir():
        return
    with open(os.path.join(config.CACHE_DIR, FILE_PARAMSETS), 'w') as fptr:
        json.dump(data.PARAMSETS, fptr)

def load_paramsets():
    """
    Load paramset data from disk into PARAMSETS.
    """
    if not check_cache_dir():
        return
    if not os.path.exists(os.path.join(config.CACHE_DIR, FILE_PARAMSETS)):
        return
    with open(os.path.join(config.CACHE_DIR, FILE_PARAMSETS)) as fptr:
        data.PARAMSETS = json.load(fptr)

def clear_paramsets():
    """
    Remove stored paramset data from disk.
    """
    check_cache_dir()
    if os.path.exists(os.path.join(config.CACHE_DIR, FILE_PARAMSETS)):
        os.unlink(os.path.join(config.CACHE_DIR, FILE_PARAMSETS))
    data.PARAMSETS.clear()

def save_names():
    """
    Save current name data in NAMES to disk.
    """
    if not check_cache_dir():
        return
    with open(os.path.join(config.CACHE_DIR, FILE_NAMES), 'w') as fptr:
        json.dump(data.NAMES, fptr)

def load_names():
    """
    Load name data from disk into NAMES.
    """
    if not check_cache_dir():
        return
    if not os.path.exists(os.path.join(config.CACHE_DIR, FILE_NAMES)):
        return
    with open(os.path.join(config.CACHE_DIR, FILE_NAMES)) as fptr:
        data.NAMES = json.load(fptr)

def clear_names():
    """
    Remove stored names data from disk.
    """
    check_cache_dir()
    if os.path.exists(os.path.join(config.CACHE_DIR, FILE_NAMES)):
        os.unlink(os.path.join(config.CACHE_DIR, FILE_NAMES))
    data.NAMES.clear()

def clear_all():
    """
    Clear all stored data.
    """
    clear_devices_raw()
    clear_paramsets()
    clear_names()
