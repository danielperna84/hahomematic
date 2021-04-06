"""
Base class for entities.
"""

import logging

import hahomematic.data
from hahomematic.const import (
    ATTR_HM_OPERATIONS,
    IGNORED_PARAMETERS,
)

LOG = logging.getLogger(__name__)

def build_entity_id(address, parameter):
    """
    Build entity id from address and parameter.
    """
    return "{}_{}".format(address.replace(':', '_'), parameter)

def create_entity(address, parameter, parameter_data, interface_id):
    if parameter in IGNORED_PARAMETERS:
        LOG.debug("create_entity: Ignoring parameter: %s (%s)", parameter, address)
        return
    LOG.debug("create_entity: Creating entity (%s, %s, %s)",
              address, parameter, interface_id)
    hahomematic.data.ENTITIES[build_entity_id(address, parameter)] = {}
