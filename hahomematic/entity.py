"""
Functions for entity creation.
"""

import logging

import hahomematic.config
import hahomematic.data
from hahomematic.helpers import generate_unique_id
from hahomematic.platforms import (
    binary_sensor,
    number,
    sensor,
    switch,
)
from hahomematic.const import (
    ATTR_HM_CONTROL,
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    IGNORED_PARAMETERS,
    TYPE_ACTION,
    TYPE_BOOL,
    TYPE_ENUM,
    TYPE_FLOAT,
    TYPE_INTEGER,
    TYPE_STRING,
)

LOG = logging.getLogger(__name__)

def create_entity(address, parameter, parameter_data, interface_id):
    """
    Helper that looks at the paramsets, decides which default
    platform should be used, and creates the required entities.
    """
    if parameter in IGNORED_PARAMETERS:
        LOG.debug("create_entity: Ignoring parameter: %s (%s)",
                  parameter, address)
        return
    if (address, parameter) not in hahomematic.data.EVENT_SUBSCRIPTIONS:
        hahomematic.data.EVENT_SUBSCRIPTIONS[(address, parameter)] = []
    unique_id = generate_unique_id(address, parameter)
    if unique_id in hahomematic.data.ENTITIES:
        LOG.warning("create_entity: Skipping %s (entity already exists)", unique_id)
        return
    # TODO: How do we handle existing entities? Entities should be removed when the server
    # receives a deleteDevices call. When the paramset has updated it should be recreated probably.
    LOG.debug("create_entity: Creating entity (%s, %s, %s)",
              address, parameter, interface_id)
    entity_id = None
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
            elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                LOG.warning("string actors currently not supported: %s %s",
                            address, parameter)
                # TODO: Implement STRING actors. Maybe input_text?
            else:
                LOG.warning("unsupported actor: %s %s %s",
                            address, parameter, parameter_data[ATTR_HM_TYPE])
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
    return entity_id

def create_custom_entity(address, device_type):
    """
    This function creates custom entities.
    """
    LOG.debug("create_custom_entity: %s (%s)", address, device_type)
