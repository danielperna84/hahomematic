# pylint: disable=line-too-long

"""
Functions for entity creation.
"""

import datetime
import logging
from abc import ABC, abstractmethod

from hahomematic.const import (
    ATTR_HM_CONTROL,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE_LIST,
    DATA_LOAD_FAIL,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    OPERATION_READ,
    TYPE_ACTION,
)
from hahomematic.devices.device_description import (
    DD_ADDRESS_PREFIX,
    DD_DEVICE,
    DD_ENTITIES,
    DD_FIELDS,
    DD_PARAM_NAME,
)

LOG = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes
class BaseEntity(ABC):
    """
    Base class for regular entities.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, platform):
        """
        Initialize the entity.
        """

        self.lastupdate = None
        self._device = device
        self.create_in_ha = not self._device.custom_device
        self._server = self._device.server
        self.interface_id = self._device.interface_id
        self.client = self._server.clients[self.interface_id]
        self.proxy = self.client.proxy
        self.unique_id = unique_id
        self.platform = platform
        self.address = address
        self.name = self.client.server.names_cache.get(self.interface_id, {}).get(
            self.address, self.unique_id
        )

        self.device_type = self._device.device_type
        self.device_class = None
        self._update_callback = None
        self._remove_callback = None

    @property
    def is_in_use(self):
        return self._update_callback is not None

    def add_entity_to_server_collections(self):
        """add entity to server collections"""
        if isinstance(self, GenericEntity):
            self._device.add_hm_entity(self)
        self._server.hm_entities[self.unique_id] = self

    def register_update_callback(self, update_callback):
        """register update callback"""
        if callable(update_callback):
            self._update_callback = update_callback

    def unregister_update_callback(self):
        """remove update callback"""
        self._update_callback = None

    def update_entity(self):
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self._update_callback is None:
            LOG.debug("Entity.update_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self._update_callback(self.unique_id)

    def register_remove_callback(self, remove_callback):
        """register remove callback"""
        if callable(remove_callback):
            self._remove_callback = remove_callback

    def unregister_remove_callback(self):
        """remove remove callback"""
        self._remove_callback = None

    def remove_entity(self):
        """
        Do what is needed when the entity has been removed.
        """
        if self._remove_callback is None:
            LOG.debug("Entity.remove_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self._remove_callback(self.unique_id)

    @property
    def device_info(self):
        """Return device specific attributes."""
        return self._device.device_info

    @abstractmethod
    def remove_event_subscriptions(self):
        """Remove existing event subscriptions"""

    @abstractmethod
    def load_data(self):
        """Load data"""

    def _set_lastupdated(self):
        self.lastupdate = datetime.datetime.now()

    def _updated_within_minutes(self, minutes=10):
        if self.lastupdate is None:
            return False
        delta = datetime.datetime.now() - self.lastupdate
        if delta.seconds < minutes * 60:
            return True
        return False

    def __str__(self):
        """
        Provide some useful information.
        """
        return f"address: {self.address}, type: {self.device_type}, name: {self.name}"


class GenericEntity(BaseEntity):
    """
    Base class for generic entities.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, parameter, parameter_data, platform):
        """
        Initialize the entity.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            platform=platform,
        )

        self.parameter = parameter
        self._parameter_data = parameter_data
        self.name = self._name()
        self.operations = self._parameter_data.get(ATTR_HM_OPERATIONS)
        self.type = self._parameter_data.get(ATTR_HM_TYPE)
        self.control = self._parameter_data.get(ATTR_HM_CONTROL)
        self.unit = self._parameter_data.get(ATTR_HM_UNIT)
        self.max = self._parameter_data.get(ATTR_HM_MAX)
        self.min = self._parameter_data.get(ATTR_HM_MIN)
        self.value_list = self._parameter_data.get(ATTR_HM_VALUE_LIST)
        self.special = self._parameter_data.get(ATTR_HM_SPECIAL)

        self._state = None
        if self.type == TYPE_ACTION:
            self._state = False

        LOG.debug("Entity.__init__: Getting current value for %s", self.unique_id)
        # pylint: disable=pointless-statement
        # self.STATE
        self._server.event_subscriptions[(self.address, self.parameter)].append(
            self.event
        )

    def event(self, interface_id, address, parameter, value):
        """
        Handle event for which this entity has subscribed.
        """
        if self._state is value:
            return

        LOG.debug(
            "Entity.event: %s, %s, %s, new: %s, old: %s",
            interface_id,
            address,
            parameter,
            value,
            self._state,
        )
        if interface_id != self.interface_id:
            LOG.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self.interface_id,
            )
            return
        if address != self.address:
            LOG.warning(
                "Entity.event: Incorrect address: %s - should be: %s",
                address,
                self.address,
            )
            return
        if parameter != self.parameter:
            LOG.warning(
                "Entity.event: Incorrect parameter: %s - should be: %s",
                parameter,
                self.parameter,
            )
            return

        self._state = value
        self.update_entity()

    @property
    @abstractmethod
    # pylint: disable=invalid-name,missing-function-docstring
    def STATE(self):
        ...

    def send_value(self, value):
        """send value to cu."""
        self.proxy.setValue(self.address, self.parameter, value)

    def _name(self):
        """generate name for entity"""
        name = self.client.server.names_cache.get(self.interface_id, {}).get(
            self.address, self.unique_id
        )
        if name.count(":") == 1:
            d_name = name.split(":")[0]
            p_name = self.parameter.title().replace("_", " ")
            c_no = name.split(":")[1]
            c_name = "" if c_no == "0" else f" ch{c_no}"
            name = f"{d_name} {p_name}{c_name}"
        else:
            d_name = name
            p_name = self.parameter.title().replace("_", " ")
            name = f"{d_name} {p_name}"
        return name

    def load_data(self):
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD
        try:
            if self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
                self._set_lastupdated()
                self.update_entity()
                return DATA_LOAD_SUCCESS
        # pylint: disable=broad-except
        except Exception as err:
            LOG.debug(
                " %s: Failed to get state for %s, %s, %s: %s",
                self.platform,
                self.device_type,
                self.address,
                self.parameter,
                err,
            )
            return DATA_LOAD_FAIL
        return DATA_NO_LOAD

    def remove_event_subscriptions(self):
        """Remove existing event subscriptions"""
        del self._server.event_subscriptions[(self.address, self.parameter)]


class CustomEntity(BaseEntity):
    """
    Base class for custom entities.
    """

    # pylint: disable=too-many-arguments
    def __init__(self, device, unique_id, address, device_desc, platform):
        """
        Initialize the entity.
        """
        super().__init__(
            device=device,
            unique_id=unique_id,
            address=address,
            platform=platform,
        )

        self.create_in_ha = True
        self._device_desc = device_desc
        self._entities: dict(str, BaseEntity) = {}
        self.channels = list(
            self._server.devices[self.interface_id][self.address].keys()
        )
        # Subscribe for all events of this device
        if self.address not in self._server.event_subscriptions_device:
            self._server.event_subscriptions_device[self.address] = []
        self._server.event_subscriptions_device[self.address].append(self.event)
        self._init_entities()

    def event(self, interface_id, address):
        """
        Handle events for this device.
        """

        if interface_id != self.interface_id:
            LOG.warning(
                "CustomEntity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self.interface_id,
            )
            return
        if address != self.address:
            LOG.warning(
                "CustomEntity.event: Incorrect address: %s - should be: %s",
                address,
                self.address,
            )
            return

        self.update_entity()

    def remove_event_subscriptions(self):
        """Remove existing event subscriptions"""
        del self._server.event_subscriptions_device[self.address]

    def _init_entities(self):
        """init entity collection"""
        for (f_name, data) in self._device_desc[DD_DEVICE][DD_FIELDS].items():
            f_address = f"{self.address}{data[DD_ADDRESS_PREFIX]}"
            p_name = data[DD_PARAM_NAME]
            entity = self._device.get_hm_entity(f_address, p_name)
            if entity:
                self._entities[f_name] = entity
        for data in self._device_desc[DD_ENTITIES].values():
            e_address = f"{self.address}{data[DD_ADDRESS_PREFIX]}"
            ep_name = data[DD_PARAM_NAME]
            entity = self._device.get_hm_entity(e_address, ep_name)
            if entity:
                entity.create_in_ha = True

    def load_data(self):
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD
        for entity in self._entities.values():
            if entity:
                entity.load_data()
                self._set_lastupdated()
        self.update_entity()
        return DATA_LOAD_SUCCESS

    def _get_field_address(self, field_name) -> str:
        """get field address"""
        entity = self._entities.get(field_name)
        if entity:
            return entity.address
        return None

    def _get_field_param(self, field_name) -> str:
        """get field param name"""
        entity = self._entities.get(field_name)
        if entity:
            return entity.parameter
        return None

    def _get_entity_value(self, field_name):
        entity = self._entities.get(field_name)
        if entity:
            return entity.STATE
        return None

    def _send_value(self, field_name, value):
        entity = self._entities.get(field_name)
        if entity:
            entity.send_value(value)
