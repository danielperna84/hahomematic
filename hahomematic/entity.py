# pylint: disable=line-too-long

"""
Functions for entity creation.
"""

import datetime
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from hahomematic.const import (
    ATTR_ADDRESS,
    ATTR_HM_CONTROL,
    ATTR_HM_MAX,
    ATTR_HM_MIN,
    ATTR_HM_OPERATIONS,
    ATTR_HM_SPECIAL,
    ATTR_HM_TYPE,
    ATTR_HM_UNIT,
    ATTR_HM_VALUE_LIST,
    ATTR_INTERFACE_ID,
    ATTR_PARAMETER,
    DATA_LOAD_FAIL,
    DATA_LOAD_SUCCESS,
    DATA_NO_LOAD,
    HIDDEN_PARAMETERS,
    OPERATION_READ,
    PARAM_UNREACH,
    TYPE_ACTION,
)
from hahomematic.devices.device_description import (
    DD_ADDRESS_PREFIX,
    DD_DEVICE,
    DD_ENTITIES,
    DD_FIELDS,
    DD_PARAM_NAME,
)
from hahomematic.helpers import get_entity_name

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
        self._entities: dict[str, GenericEntity] = {}
        self._server = self._device.server
        self._interface_id = self._device.interface_id
        self.client = self._server.clients[self._interface_id]
        self.proxy = self.client.proxy
        self.unique_id = unique_id
        self.platform = platform
        self.address = address
        self.name = self.client.server.names_cache.get(self._interface_id, {}).get(
            self.address, self.unique_id
        )

        self.device_type = self._device.device_type
        self.device_class = None
        self._update_callback = None
        self._remove_callback = None

    def _init_entities(self) -> None:
        """Init the supporting entity collection."""
        unreach = self._device.get_hm_entity(f"{self.address}:0", PARAM_UNREACH)
        if unreach:
            self._entities[PARAM_UNREACH] = unreach

    @property
    def available(self) -> bool:
        """Return the availabiltity of the device."""
        return self._device.available

    @property
    def device_info(self) -> dict[str, str]:
        """Return device specific attributes."""
        return self._device.device_info

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        return {ATTR_INTERFACE_ID: self._interface_id, ATTR_ADDRESS: self.address}

    def add_to_collections(self) -> None:
        """add entity to server collections"""
        if isinstance(self, GenericEntity):
            self._device.add_hm_entity(self)
        self._server.hm_entities[self.unique_id] = self

    def register_update_callback(self, update_callback) -> None:
        """register update callback"""
        if callable(update_callback):
            self._update_callback = update_callback

    def unregister_update_callback(self) -> None:
        """remove update callback"""
        self._update_callback = None

    def update_entity(self) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        if self._update_callback is None:
            LOG.debug("Entity.update_entity: No callback defined.")
            return
        self._set_lastupdated()
        # pylint: disable=not-callable
        self._update_callback(self.unique_id)

    def register_remove_callback(self, remove_callback) -> None:
        """register remove callback"""
        if callable(remove_callback):
            self._remove_callback = remove_callback

    def unregister_remove_callback(self) -> None:
        """remove remove callback"""
        self._remove_callback = None

    def remove_entity(self) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        if self._remove_callback is None:
            LOG.debug("Entity.remove_entity: No callback defined.")
            return
        # pylint: disable=not-callable
        self._remove_callback(self.unique_id)

    @abstractmethod
    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""

    @abstractmethod
    def load_data(self) -> None:
        """Load data"""

    def _set_lastupdated(self) -> None:
        self.lastupdate = datetime.datetime.now()

    def _updated_within_minutes(self, minutes=10) -> bool:
        if self.lastupdate is None:
            return False
        delta = datetime.datetime.now() - self.lastupdate
        if delta.seconds < minutes * 60:
            return True
        return False

    def __str__(self) -> str:
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
        # Do not create some Entities in HA
        if self.parameter in HIDDEN_PARAMETERS:
            self.create_in_ha = False
        self._parameter_data = parameter_data
        self._assign_parameter_data()

        self.name = get_entity_name(
            server=self._server,
            interface_id=self._interface_id,
            address=self.address,
            parameter=self.parameter,
            unique_id=self.unique_id,
        )

        self._state = None
        if self.type == TYPE_ACTION:
            self._state = False

        # Subscribe for all events of this device
        if (
            self.address,
            self.parameter,
        ) not in self._server.entity_event_subscriptions:
            self._server.entity_event_subscriptions[(self.address, self.parameter)] = []
        self._server.entity_event_subscriptions[(self.address, self.parameter)].append(
            self.event
        )
        self._init_entities()

    def _assign_parameter_data(self):
        """Assign parameter data to instance variables."""
        self.operations = self._parameter_data.get(ATTR_HM_OPERATIONS)
        self.type = self._parameter_data.get(ATTR_HM_TYPE)
        self.control = self._parameter_data.get(ATTR_HM_CONTROL)
        self.unit = self._parameter_data.get(ATTR_HM_UNIT)
        self.max = self._parameter_data.get(ATTR_HM_MAX)
        self.min = self._parameter_data.get(ATTR_HM_MIN)
        self.value_list = self._parameter_data.get(ATTR_HM_VALUE_LIST)
        self.special = self._parameter_data.get(ATTR_HM_SPECIAL)

    def update_parameter_data(self):
        """Update parameter data"""
        self._assign_parameter_data()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        state_attr = super().extra_state_attributes
        state_attr[ATTR_PARAMETER] = self.parameter
        return state_attr

    def event(self, interface_id, address, parameter, value) -> None:
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
        if interface_id != self._interface_id:
            LOG.warning(
                "Entity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
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

    def send_value(self, value) -> None:
        """send value to ccu."""
        try:
            self.proxy.setValue(self.address, self.parameter, value)
        # pylint: disable=broad-except
        except Exception:
            LOG.exception(
                "generic_entity: Failed to set state for: %s, %s, %s, %s",
                self.device_type,
                self.address,
                self.parameter,
                value,
            )

    def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD
        try:

            if self.operations & OPERATION_READ:
                self._state = self.proxy.getValue(self.address, self.parameter)
                self.update_entity()

            for entity in self._entities.values():
                if entity:
                    entity.load_data()

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

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._server.entity_event_subscriptions[(self.address, self.parameter)]


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
        self.channels = list(
            self._server.devices[self._interface_id][self.address].keys()
        )
        # Subscribe for all events of this device
        if self.address not in self._server.device_event_subscriptions:
            self._server.device_event_subscriptions[self.address] = []
        self._server.device_event_subscriptions[self.address].append(self.event)
        self._init_entities()

    def event(self, interface_id, address) -> None:
        """
        Handle events for this device.
        """

        if interface_id != self._interface_id:
            LOG.warning(
                "CustomEntity.event: Incorrect interface_id: %s - should be: %s",
                interface_id,
                self._interface_id,
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

    def remove_event_subscriptions(self) -> None:
        """Remove existing event subscriptions"""
        del self._server.device_event_subscriptions[self.address]

    def _init_entities(self) -> None:
        """init entity collection"""
        super()._init_entities()
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

    def load_data(self) -> int:
        """Load data"""
        if self._updated_within_minutes():
            return DATA_NO_LOAD

        for entity in self._entities.values():
            if entity:
                entity.load_data()

        self.update_entity()
        return DATA_LOAD_SUCCESS

    def _get_field_address(self, field_name) -> Optional[str]:
        """get field address"""
        entity = self._entities.get(field_name)
        if entity:
            return entity.address
        return None

    def _get_field_param(self, field_name) -> Optional[str]:
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

    def _send_value(self, field_name, value) -> None:
        entity = self._entities.get(field_name)
        if entity:
            entity.send_value(value)
