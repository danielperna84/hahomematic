# pylint: disable=line-too-long

"""
Module for the Device class
"""
import logging

from hahomematic import config, data
import hahomematic.devices
from hahomematic.const import (
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    HH_EVENT_DEVICES_CREATED,
    IGNORED_PARAMETERS,
    OPERATION_EVENT,
    OPERATION_WRITE,
    PARAMSET_VALUES,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
)
from hahomematic.helpers import generate_unique_id
from hahomematic.platforms.binary_sensor import binary_sensor
from hahomematic.platforms.input_select import input_select
from hahomematic.platforms.input_text import input_text
from hahomematic.platforms.number import number
from hahomematic.platforms.sensor import sensor
from hahomematic.platforms.switch import switch

LOG = logging.getLogger(__name__)


class Device:
    """
    Object to hold information about a device and associated entities.
    """

    def __init__(self, interface_id, address):
        """
        Initialize the device object.
        """
        self.interface_id = interface_id
        self.client = data.CLIENTS[self.interface_id]
        self._server = self.client.server
        self.address = address
        self.channels = self._server.devices[self.interface_id][self.address]
        LOG.debug(
            "Device.__init__: Initializing device: %s, %s",
            self.interface_id,
            self.address,
        )

        self.entities = set()
        self.device_type = self._server.devices_raw_dict[self.interface_id][
            self.address
        ][ATTR_HM_TYPE]
        if self.address in self._server.names_cache.get(self.interface_id, {}):
            self.name = self._server.names_cache[self.interface_id][self.address]
        else:
            LOG.info(
                "Device.__init__: Using auto-generated name for %s %s",
                self.device_type,
                self.address,
            )
            self.name = f"{self.device_type}_{self.address}"

        LOG.debug(
            "Device.__init__: Initialized device: %s, %s, %s, %s",
            self.interface_id,
            self.address,
            self.device_type,
            self.name,
        )

    def __str__(self):
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}"

    def create_entities(self):
        """
        Create the entities associated to this device.
        """
        new_entities = set()
        for channel in self.channels:
            if channel not in self._server.paramsets_cache[self.interface_id]:
                LOG.warning(
                    "Device.create_entities: Skipping channel %s, missing paramsets.",
                    channel,
                )
                continue
            for paramset in self._server.paramsets_cache[self.interface_id][channel]:
                if paramset != PARAMSET_VALUES:
                    continue
                for parameter, parameter_data in self._server.paramsets_cache[
                    self.interface_id
                ][channel][paramset].items():
                    if not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
                        LOG.debug(
                            "Device.create_entities: Skipping %s (no event)", parameter
                        )
                        continue
                    unique_id = create_entity(
                        channel, parameter, parameter_data, self.interface_id
                    )
                    if unique_id is not None:
                        self._server.ha_devices[self.address].entities.add(unique_id)
                        new_entities.add(unique_id)
        if self.device_type in hahomematic.devices.DEVICES:
            LOG.debug(
                "Device.create_entities: Handling custom device integration: %s, %s, %s",
                self.interface_id,
                self.address,
                self.device_type,
            )
            # Call the custom device / entity creation function.
            for u_id in hahomematic.devices.DEVICES[self.device_type](
                self.interface_id, self.address
            ):
                new_entities.add(u_id)
        return new_entities


def create_devices(server):
    """
    Trigger creation of the objects that expose the functionality.
    """
    new_devices = set()
    new_entities = set()
    for interface_id, client in data.CLIENTS.items():
        if not client:
            LOG.warning(
                "create_devices: Skipping interface %s, missing client.", interface_id
            )
            continue
        if interface_id not in server.paramsets_cache:
            LOG.warning(
                "create_devices: Skipping interface %s, missing paramsets.",
                interface_id,
            )
            continue
        for device_address in server.devices[interface_id]:
            # Do we check for duplicates here? For now we do.
            if device_address in server.ha_devices:
                LOG.warning(
                    "create_devices: Skipping device %s on %s, already exists.",
                    device_address,
                    interface_id,
                )
                continue
            try:
                server.ha_devices[device_address] = Device(interface_id, device_address)
                new_devices.add(device_address)
            except Exception:
                LOG.exception(
                    "create_devices: Failed to create device: %s, %s",
                    interface_id,
                    device_address,
                )
            try:
                new_entities.update(server.ha_devices[device_address].create_entities())
            except Exception:
                LOG.exception(
                    "create_devices: Failed to create entities: %s, %s",
                    interface_id,
                    device_address,
                )
    if callable(config.CALLBACK_SYSTEM):
        # pylint: disable=not-callable
        config.CALLBACK_SYSTEM(HH_EVENT_DEVICES_CREATED, new_devices, new_entities)


# pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
def create_entity(address, parameter, parameter_data, interface_id):
    """
    Helper that looks at the paramsets, decides which default
    platform should be used, and creates the required entities.
    """
    server = data.CLIENTS[interface_id].server
    if parameter in IGNORED_PARAMETERS:
        LOG.debug("create_entity: Ignoring parameter: %s (%s)", parameter, address)
        return None
    if (address, parameter) not in server.event_subscriptions:
        server.event_subscriptions[(address, parameter)] = []
    unique_id = generate_unique_id(address, parameter)
    # TODO: How do we handle existing entities? Entities should be removed when the server
    # receives a deleteDevices call. When the paramset has updated it should be recreated probably.
    LOG.debug(
        "create_entity: Creating entity for %s, %s, %s",
        address,
        parameter,
        interface_id,
    )
    if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
        if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
            LOG.debug("create_entity: switch (action): %s %s", address, parameter)
            if unique_id in server.entities:
                LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                return None
            server.entities[unique_id] = switch(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                LOG.debug("create_entity: switch: %s %s", address, parameter)
                if unique_id in server.entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                server.entities[unique_id] = switch(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                LOG.debug("create_entity: input_select: %s %s", address, parameter)
                if unique_id in server.entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                server.entities[unique_id] = input_select(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER]:
                LOG.debug("create_entity: number: %s %s", address, parameter)
                if unique_id in server.entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                server.entities[unique_id] = number(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                LOG.debug("create_entity: input_text: %s %s", address, parameter)
                if unique_id in server.entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                server.entities[unique_id] = input_text(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            else:
                LOG.warning(
                    "unsupported actor: %s %s %s",
                    address,
                    parameter,
                    parameter_data[ATTR_HM_TYPE],
                )
    else:
        if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
            LOG.debug("create_entity: binary_sensor: %s %s", address, parameter)
            if unique_id in server.entities:
                LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                return None
            server.entities[unique_id] = binary_sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            LOG.debug("create_entity: sensor: %s %s", address, parameter)
            if unique_id in server.entities:
                LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                return None
            server.entities[unique_id] = sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
    return unique_id
