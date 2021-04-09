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
    # TODO: How do we handle existing entities? Entities should be removed when the server
    # receives a deleteDevices call. When the paramset has updated it should be recreated probably.
    LOG.debug("create_entity: Creating entity (%s, %s, %s)",
              address, parameter, interface_id)
    entity_id = None
    if parameter_data[ATTR_HM_OPERATIONS] & 2:
        if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
            LOG.debug("create_entity: switch (action): %s %s", address, parameter)
            entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
            if entity_id in hahomematic.data.ENTITIES:
                LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                return
            hahomematic.data.ENTITIES[entity_id] = switch(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                LOG.debug("create_entity: switch: %s %s", address, parameter)
                entity_id = "switch.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return
                hahomematic.data.ENTITIES[entity_id] = switch(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                LOG.debug("create_entity: input_select: %s %s", address, parameter)
                entity_id = "input_select.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return
                hahomematic.data.ENTITIES[entity_id] = input_select(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER]:
                LOG.debug("create_entity: number: %s %s", address, parameter)
                entity_id = "number.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return
                hahomematic.data.ENTITIES[entity_id] = number(
                    interface_id, unique_id, address, parameter, parameter_data
                )
            elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                LOG.debug("create_entity: input_text: %s %s", address, parameter)
                entity_id = "input_text.{}".format(unique_id).replace('-', '_').lower()
                if entity_id in hahomematic.data.ENTITIES:
                    LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                    return
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
                return
            hahomematic.data.ENTITIES[entity_id] = binary_sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
        else:
            LOG.debug("create_entity: sensor: %s %s", address, parameter)
            entity_id = "sensor.{}".format(unique_id).replace('-', '_').lower()
            if entity_id in hahomematic.data.ENTITIES:
                LOG.debug("create_entity: Skipping %s (already exists)", entity_id)
                return
            hahomematic.data.ENTITIES[entity_id] = sensor(
                interface_id, unique_id, address, parameter, parameter_data
            )
    return entity_id

def create_custom_entity(address, device_type):
    """
    This function creates custom entities.
    """
    LOG.debug("create_custom_entity: %s (%s)", address, device_type)
