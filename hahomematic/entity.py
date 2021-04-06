"""
Functions for entity creation.
"""

import logging

import hahomematic.data
from hahomematic.platforms import (
    binary_sensor,
    number,
    sensor,
    switch,
)
from hahomematic.const import (
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    IGNORED_PARAMETERS,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
)

LOG = logging.getLogger(__name__)

def generate_unique_id(address, parameter):
    """
    Build unique id from address and parameter.
    """
    return "{}_{}".format(address.replace(':', '_'), parameter)

def create_entity(address, parameter, parameter_data, interface_id):
    """
    Helper that looks at the paramsets, decides which default
    platform should be used, and creates the required entities.
    """
    if parameter in IGNORED_PARAMETERS:
        LOG.debug("create_entity: Ignoring parameter: %s (%s)", parameter, address)
        return
    unique_id = generate_unique_id(address, parameter)
    if unique_id in hahomematic.data.ENTITIES:
        LOG.warning("create_entity: Skipping %s (entity already exists)", unique_id)
        return
    # TODO: How do we handle existing entities? Entities should be removed when the server
    # receives a deleteDevices call. When the paramset has updated it should be recreated probably.
    LOG.debug("create_entity: Creating entity (%s, %s, %s)",
              address, parameter, interface_id)
    if parameter_data[ATTR_HM_OPERATIONS] & 2:
        if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
            LOG.debug("switch (action): %s %s", address, parameter)
            entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
            hahomematic.data.ENTITIES[entity_id] = switch(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                LOG.debug("switch: %s %s", address, parameter)
                entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
                hahomematic.data.ENTITIES[entity_id] = switch(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER, TYPE_ENUM]:
                LOG.debug("number: %s %s", address, parameter)
                entity_id = "number.{}".format(unique_id).replace('-', '_').lower()
                hahomematic.data.ENTITIES[entity_id] = number(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            else:
                LOG.warning("unsupported actor: %s %s", address, parameter)
    else:
        if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
            LOG.debug("binary_sensor: %s %s", address, parameter)
            entity_id = "binary_sensor.{}".format(unique_id).replace('-', '_').lower()
            hahomematic.data.ENTITIES[entity_id] = binary_sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            LOG.debug("sensor: %s %s", address, parameter)
            entity_id = "sensor.{}".format(unique_id).replace('-', '_').lower()
            hahomematic.data.ENTITIES[entity_id] = sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )

def create_custom_entity(address, device_type):
    """
    This function creates custom entities.
    """
    LOG.debug("create_custom_entity: %s (%s)", address, device_type)
