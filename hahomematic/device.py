# pylint: disable=line-too-long

"""
Module for the Device class
"""
import logging

import hahomematic.devices
from hahomematic import config
from hahomematic.const import (
    ATTR_HM_FIRMWARE,
    ATTR_HM_OPERATIONS,
    ATTR_HM_TYPE,
    HA_DOMAIN,
    HH_EVENT_DEVICES_CREATED,
    IGNORED_PARAMETERS,
    IGNORED_PARAMETERS_WILDCARDS,
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
from hahomematic.entity import BaseEntity, GenericEntity
from hahomematic.helpers import generate_unique_id
from hahomematic.platforms.binary_sensor import HM_Binary_Sensor
from hahomematic.platforms.number import HM_Number
from hahomematic.platforms.select import HM_Select
from hahomematic.platforms.sensor import HM_Sensor
from hahomematic.platforms.switch import HM_Switch

LOG = logging.getLogger(__name__)


class Device:
    """
    Object to hold information about a device and associated entities.
    """

    def __init__(self, server, interface_id, address):
        """
        Initialize the device object.
        """
        self.server = server
        self.interface_id = interface_id
        self.client = self.server.clients[self.interface_id]
        self.address = address
        self.channels = self.server.devices[self.interface_id][self.address]
        LOG.debug(
            "Device.__init__: Initializing device: %s, %s",
            self.interface_id,
            self.address,
        )

        self.entities: dict(dict(str, str), BaseEntity) = {}
        self.device_type = self.server.devices_raw_dict[self.interface_id][
            self.address
        ][ATTR_HM_TYPE]
        # marker if device will be created as custom device
        self.custom_device = (
            True if self.device_type in hahomematic.devices.DEVICES else False
        )
        self.firmware = self.server.devices_raw_dict[self.interface_id][self.address][
            ATTR_HM_FIRMWARE
        ]
        if self.address in self.server.names_cache.get(self.interface_id, {}):
            self.name = self.server.names_cache[self.interface_id][self.address]
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

    def add_hm_entity(self, hm_entity: GenericEntity):
        """add an hm entity to a device"""
        if isinstance(hm_entity, GenericEntity):
            self.entities[(hm_entity.address, hm_entity.parameter)] = hm_entity

    def get_hm_entity(self, address, parameter) -> GenericEntity:
        """return a hm_entity from device"""
        return self.entities.get((address, parameter))

    def __str__(self):
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self.device_type}, name: {self.name}, entities: {self.entities}"

    @property
    def device_info(self):
        """Return device specific attributes."""
        return {
            "identifiers": {(HA_DOMAIN, self.address)},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": self.device_type,
            "sw_version": self.firmware,
            "via_device": (HA_DOMAIN, self.interface_id),
        }

    def create_entities(self) -> dict[str, GenericEntity]:
        """
        Create the entities associated to this device.
        """
        new_entities: GenericEntity = set()
        for channel in self.channels:
            if channel not in self.server.paramsets_cache[self.interface_id]:
                LOG.warning(
                    "Device.create_entities: Skipping channel %s, missing paramsets.",
                    channel,
                )
                continue
            for paramset in self.server.paramsets_cache[self.interface_id][channel]:
                if paramset != PARAMSET_VALUES:
                    continue
                for parameter, parameter_data in self.server.paramsets_cache[
                    self.interface_id
                ][channel][paramset].items():
                    if not parameter_data[ATTR_HM_OPERATIONS] & OPERATION_EVENT:
                        LOG.debug(
                            "Device.create_entities: Skipping %s (no event)", parameter
                        )
                        continue
                    entity = self.create_entity(
                        address=channel,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                    if entity is not None:
                        new_entities.add(entity)
        # create custom entities
        if self.custom_device:
            LOG.debug(
                "Device.create_entities: Handling custom device integration: %s, %s, %s",
                self.interface_id,
                self.address,
                self.device_type,
            )
            # Call the custom device / entity creation function.
            for custom_entity in hahomematic.devices.DEVICES[self.device_type](
                self, self.address
            ):
                new_entities.add(custom_entity)
        return new_entities

    def create_entity(self, address, parameter, parameter_data) -> GenericEntity:
        """
        Helper that looks at the paramsets, decides which default
        platform should be used, and creates the required entities.
        """
        if parameter in IGNORED_PARAMETERS or parameter.endswith(
            tuple(IGNORED_PARAMETERS_WILDCARDS)
        ):
            LOG.debug("create_entity: Ignoring parameter: %s (%s)", parameter, address)
            return None
        if (address, parameter) not in self.server.event_subscriptions:
            self.server.event_subscriptions[(address, parameter)] = []
        if (address, parameter) not in self.entities:
            self.entities[(address, parameter)] = []

        unique_id = generate_unique_id(address, parameter)

        LOG.debug(
            "create_entity: Creating entity for %s, %s, %s",
            address,
            parameter,
            self.interface_id,
        )
        entity = None
        if parameter_data[ATTR_HM_OPERATIONS] & OPERATION_WRITE:
            if parameter_data[ATTR_HM_TYPE] == TYPE_ACTION:
                LOG.debug("create_entity: switch (action): %s %s", address, parameter)
                if unique_id in self.server.hm_entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                entity = HM_Switch(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            else:
                if parameter_data[ATTR_HM_TYPE] == TYPE_BOOL:
                    LOG.debug("create_entity: switch: %s %s", address, parameter)
                    if unique_id in self.server.hm_entities:
                        LOG.debug(
                            "create_entity: Skipping %s (already exists)", unique_id
                        )
                        return None
                    entity = HM_Switch(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_ENUM:
                    LOG.debug("create_entity: select: %s %s", address, parameter)
                    if unique_id in self.server.hm_entities:
                        LOG.debug(
                            "create_entity: Skipping %s (already exists)", unique_id
                        )
                        return None
                    entity = HM_Select(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] in [TYPE_FLOAT, TYPE_INTEGER]:
                    LOG.debug("create_entity: number: %s %s", address, parameter)
                    if unique_id in self.server.hm_entities:
                        LOG.debug(
                            "create_entity: Skipping %s (already exists)", unique_id
                        )
                        return None
                    entity = HM_Number(
                        device=self,
                        unique_id=unique_id,
                        address=address,
                        parameter=parameter,
                        parameter_data=parameter_data,
                    )
                elif parameter_data[ATTR_HM_TYPE] == TYPE_STRING:
                    # There is currently no entity platform in HA for this.
                    return None
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
                if unique_id in self.server.hm_entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                entity = HM_Binary_Sensor(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
            else:
                LOG.debug("create_entity: sensor: %s %s", address, parameter)
                if unique_id in self.server.hm_entities:
                    LOG.debug("create_entity: Skipping %s (already exists)", unique_id)
                    return None
                entity = HM_Sensor(
                    device=self,
                    unique_id=unique_id,
                    address=address,
                    parameter=parameter,
                    parameter_data=parameter_data,
                )
        if entity:
            entity.add_entity_to_server_collections()
        return entity


# pylint: disable=too-many-return-statements,too-many-branches,too-many-statements
def create_devices(server):
    """
    Trigger creation of the objects that expose the functionality.
    """
    new_devices = set()
    new_entities = set()
    for interface_id, client in server.clients.items():
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
            device: Device = None
            if device_address in server.hm_devices:
                LOG.debug(
                    "create_devices: Skipping device %s on %s, already exists.",
                    device_address,
                    interface_id,
                )
                continue
            try:
                device = Device(server, interface_id, device_address)
                new_devices.add(device_address)
                server.hm_devices[device_address] = device
            except Exception:
                LOG.exception(
                    "create_devices: Failed to create device: %s, %s",
                    interface_id,
                    device_address,
                )
            try:
                new_entities.update(device.create_entities())
            except Exception:
                LOG.exception(
                    "create_devices: Failed to create entities: %s, %s",
                    interface_id,
                    device_address,
                )
    if callable(server.callback_system):
        # pylint: disable=not-callable
        server.callback_system(HH_EVENT_DEVICES_CREATED, new_devices, new_entities)
