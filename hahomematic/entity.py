# pylint: disable=line-too-long

"""
Functions for entity creation.
"""

import logging

import hahomematic.config
import hahomematic.data
from hahomematic.helpers import generate_unique_id
from hahomematic.platforms import (
    binary_sensor,
    input_select,
    input_text,
    number,
    sensor,
    switch,
)
from hahomematic.const import (
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    IGNORED_PARAMETERS,
    OPERATION_WRITE,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
)

LOG = logging.getLogger(__name__)

class Device():
    """
    Object to hold information about a device and associated entities.
    """
    def __init__(self, interface_id, address):
        """
        Initialize the device object.
        """
        self.interface_id = interface_id
        self.address = address
        self.channels = hahomematic.data.DEVICES[self.interface_id][self.address]
        LOG.debug("Device.__init__: Initializing device: %s, %s",
                  self.interface_id, self.address)
        self.entities = set()
        self.device_type = hahomematic.data.DEVICES_RAW_DICT[self.interface_id][self.address][ATTR_HM_TYPE]
        if self.address in hahomematic.data.NAMES.get(self.interface_id, {}):
            self.name = hahomematic.data.NAMES[self.interface_id][self.address]
        else:
            LOG.info("Device.__init__: Using auto-generated name for %s %s", self.device_type, self.address)
            self.name = "{}_{}".format(self.device_type, self.address)
        self.client = hahomematic.data.CLIENTS[self.interface_id]
        LOG.debug("Device.__init__: Initialized device: %s, %s, %s, %s",
                  self.interface_id, self.address, self.device_type, self.name)

    def __str__(self):
        """
        Provide some useful information.
        """
        return f'address: {self.address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}'

    def create_entities(self):
        """
        Create the entities associated to this device.
        """
        for channel in self.channels:
            if channel not in hahomematic.data.PARAMSETS[self.interface_id]:
                LOG.warning("Device.create_entities: Skipping channel %s, missing paramsets.", channel)
                continue
            for paramset in hahomematic.data.PARAMSETS[self.interface_id][channel]:
                for parameter, parameter_data in hahomematic.data.PARAMSETS[self.interface_id][channel][paramset].items():
                    if not parameter_data[ATTR_HM_OPERATIONS] & 4 and \
                    not parameter_data[ATTR_HM_TYPE] == TYPE_ACTION and \
                    not parameter_data[ATTR_HM_TYPE] == TYPE_FLOAT:
                        LOG.debug("Device.create_entities: Skipping %s (no event, no action, no float)",
                                  parameter)
                        continue
                    entity_id = create_entity(channel, parameter, parameter_data, self.interface_id)
                    if entity_id is not None:
                        hahomematic.data.HA_DEVICES[self.address].entities.add(entity_id)
        # TODO: Hook for custom entity based on `self.device_type`

# pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
def create_entity(address, parameter, parameter_data, interface_id):
    """
    Helper that looks at the paramsets, decides which default
    platform should be used, and creates the required entities.
    """
    if parameter in IGNORED_PARAMETERS:
        LOG.debug("create_entity: Ignoring parameter: %s (%s)",
                  parameter, address)
        return None
    if (address, parameter) not in hahomematic.data.EVENT_SUBSCRIPTIONS:
        hahomematic.data.EVENT_SUBSCRIPTIONS[(address, parameter)] = []
    unique_id = generate_unique_id(address, parameter)
    # TODO: How do we handle existing entities? Entities should be removed when the server
    # receives a deleteDevices call. When the paramset has updated it should be recreated probably.
    LOG.debug("create_entity: Creating entity (%s, %s, %s)",
              address, parameter, interface_id)
    entity_id = None
    if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
        if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
            LOG.debug("create_entity: switch (action): %s %s", address, parameter)
            entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
            if entity_id in hahomematic.data.ENTITIES:
                LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                return None
            hahomematic.data.ENTITIES[entity_id] = switch(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                LOG.debug("create_entity: switch: %s %s", address, parameter)
                entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return None
                hahomematic.data.ENTITIES[entity_id] = switch(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                LOG.debug("create_entity: input_select: %s %s", address, parameter)
                entity_id = "input_select.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return None
                hahomematic.data.ENTITIES[entity_id] = input_select(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER]:
                LOG.debug("create_entity: number: %s %s", address, parameter)
                entity_id = "number.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return None
                hahomematic.data.ENTITIES[entity_id] = number(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                LOG.debug("create_entity: input_text: %s %s", address, parameter)
                entity_id = "input_text.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return None
                hahomematic.data.ENTITIES[entity_id] = input_text(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            else:
                LOG.warning("unsupported actor: %s %s %s",
                            address, parameter, parameter_data[ATTR_HM_TYPE])
    else:
        if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
            LOG.debug("create_entity: binary_sensor: %s %s", address, parameter)
            entity_id = "binary_sensor.{}".format(unique_id).replace('-', '_').lower()
            if entity_id in hahomematic.data.ENTITIES:
                LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                return None
            hahomematic.data.ENTITIES[entity_id] = binary_sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            LOG.debug("create_entity: sensor: %s %s", address, parameter)
            entity_id = "sensor.{}".format(unique_id).replace('-', '_').lower()
            if entity_id in hahomematic.data.ENTITIES:
                LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                return None
            hahomematic.data.ENTITIES[entity_id] = sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
    return entity_id

def create_custom_entity(address, device_type):
    """
    This function creates custom entities.
    """
    LOG.debug("create_custom_entity: %s (%s)", address, device_type)
