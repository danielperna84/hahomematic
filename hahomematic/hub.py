"""Module for the hub"""
from abc import ABC
import datetime
import logging
from typing import Any

from hahomematic.const import HA_DOMAIN
from hahomematic.helpers import generate_unique_id

_LOGGER = logging.getLogger(__name__)

EXCLUDED_FROM_SENSOR_PREFIXES = [
    "sv",
    "WatchDog",
    "DutyCycle",
    "pcCCUID",
    "RF-Gateway-Alarm",
]


class BaseHubEntity(ABC):
    """
    Base class for hub entities.
    """

    def __init__(self, central, unique_id, name, state=None):
        """
        Initialize the entity.
        """
        self._central = central
        self.unique_id = unique_id
        self.name = name
        self._state = state
        self.last_update = None
        self._update_callbacks = []
        self._remove_callbacks = []
        self.create_in_ha = True

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central.available

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        return {}

    @property
    def state(self):
        """Return the state of the entity."""
        return self._state

    # pylint: disable=no-self-use
    async def load_data(self):
        """Do not load data for the hub here."""
        return

    # pylint: disable=no-self-use
    async def fetch_data(self):
        """fetch data for the hub."""
        return

    def register_update_callback(self, update_callback) -> None:
        """register update callback"""
        if callable(update_callback):
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback) -> None:
        """remove update callback"""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_entity(self, *args) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(self.unique_id)

    def register_remove_callback(self, remove_callback) -> None:
        """register remove callback"""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback) -> None:
        """remove remove callback"""
        if remove_callback in self._remove_callbacks:
            self._remove_callbacks.remove(remove_callback)

    def remove_entity(self) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        for _callback in self._remove_callbacks:
            _callback(self.unique_id)

    def _set_last_update(self) -> None:
        self.last_update = datetime.datetime.now()


class HmSystemVariable(BaseHubEntity):
    """Class for a homematic system variable."""

    def __init__(self, central, name, state):
        self._hub = central.hub
        unique_id = generate_unique_id(central.instance_name, name, prefix="hub")
        super().__init__(central=central, unique_id=unique_id, name=name, state=state)

    @property
    def device_info(self) -> dict[str, str]:
        """Return device specific attributes."""
        return self._hub.device_info

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False

    async def set_state(self, value):
        """Set variable value on CCU/Homegear."""
        old_state = self._state
        if isinstance(old_state, bool):
            value = bool(value)
        elif isinstance(old_state, float):
            value = float(value)
        elif isinstance(old_state, int):
            value = int(value)
        elif isinstance(old_state, str):
            value = str(value)

        self._state = value
        self.update_entity()


class HmHub(BaseHubEntity):
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central, use_entities=False):
        """Initialize HomeMatic hub."""
        unique_id = generate_unique_id(central.instance_name, prefix="hub")
        name = central.instance_name
        super().__init__(central, unique_id, name)
        self.hub_entities: dict[str, HmSystemVariable] = {}
        self._variables: dict[str, Any] = {}
        self._use_entities = use_entities

    @property
    def device_info(self) -> dict[str, str]:
        """Return device specific attributes."""
        return {
            "config_entry_id": self._central.entry_id,
            "identifiers": {(HA_DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": self._central.model,
            "sw_version": self._central.version,
            "via_device": (HA_DOMAIN, self._central.instance_name),
        }

    @property
    def should_poll(self) -> bool:
        """polling needed."""
        return True

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._variables.copy()

    async def fetch_data(self):
        """fetch data for the hub."""
        await self._update_hub_state()
        await self._update_entities()

    async def _update_hub_state(self):
        """Retrieve latest state."""
        service_message = await self._central.get_service_messages()
        state = 0 if service_message is None else len(service_message)

        if self._state != state:
            self._state = state
            self.update_entity()

    async def _update_entities(self):
        """Retrieve all variable data and update hmvariable states."""
        self._variables.clear()
        variables = await self._central.get_all_system_variables()
        if not variables:
            return
        for name, value in variables.items():
            if not self._use_entities or name.startswith(
                tuple(EXCLUDED_FROM_SENSOR_PREFIXES)
            ):
                self._variables[name] = value
                continue
            entity: HmSystemVariable = self.hub_entities.get(name)
            if entity:
                await entity.set_state(value)
            else:
                self._create_system_variable(name, value)

        # check if hub_entities can be deletes
        del_entities = []
        for entity_name in self.hub_entities:
            if entity_name not in variables.keys():
                del_entities.append(entity_name)

        # remove entity if necessary
        for to_delete in del_entities:
            del self.hub_entities[to_delete]
        self.update_entity()

    def _create_system_variable(self, name, value):
        """Create system variable as entity."""
        variable = HmSystemVariable(central=self._central, name=name, state=value)
        self.hub_entities[name] = variable

    async def set_system_variable(self, name, value):
        """Set variable value on CCU/Homegear."""
        if name not in self.hub_entities:
            _LOGGER.error("Variable %s not found on %s", name, self.name)
            return

        await self._central.set_system_variable(name, value)


class HmDummyHub(BaseHubEntity):
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central, use_entities=False):
        """Initialize HomeMatic hub."""
        unique_id = generate_unique_id(central.instance_name, prefix="hub")
        name = central.instance_name
        super().__init__(central, unique_id, name)
        self.hub_entities: dict[str, BaseHubEntity] = {}
        self._use_entities = use_entities

    @property
    def device_info(self) -> dict[str, str]:
        """Return device specific attributes."""
        return {
            "config_entry_id": self._central.entry_id,
            "identifiers": {(HA_DOMAIN, self.unique_id)},
            "name": self.name,
            "manufacturer": "eQ-3",
            "model": self._central.model,
            "sw_version": self._central.version,
            "via_device": (HA_DOMAIN, self._central.instance_name),
        }

    @property
    def should_poll(self) -> bool:
        """polling needed."""
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {}

    async def fetch_data(self):
        """do not fetch data for the hub."""
        return

    # pylint: disable=no-self-use
    async def set_system_variable(self, name, value):
        """Do not set variable value on CCU/Homegear."""
        return
