"""Module for the hub"""
from __future__ import annotations

from abc import ABC
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from slugify import slugify

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    BACKEND_CCU,
    HUB_ADDRESS,
    INIT_DATETIME,
    SYSVAR_ADDRESS,
    SYSVAR_TYPE_LIST,
    HmEntityUsage,
    HmPlatform,
)
from hahomematic.helpers import (
    HmDeviceInfo,
    SystemVariableData,
    generate_unique_id,
    parse_sys_var,
)

_LOGGER = logging.getLogger(__name__)

EXCLUDED_FROM_SENSOR = [
    "pcCCUID",
]

EXCLUDED = [
    "OldVal",
]

SERVICE_MESSAGES = "Servicemeldungen"


class BaseHubEntity(ABC):
    """
    Base class for hub entities.
    """

    def __init__(
        self,
        central: hm_central.CentralUnit,
        unique_id: str,
        name: str,
    ):
        """
        Initialize the entity.
        """
        self._central = central
        self.unique_id = unique_id
        self.name = name
        self.last_update: datetime = INIT_DATETIME
        self._update_callbacks: list[Callable] = []
        self._remove_callbacks: list[Callable] = []
        self.create_in_ha: bool = True
        self.should_poll = False
        self.usage = HmEntityUsage.ENTITY

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central.available

    @property
    def device_information(self) -> HmDeviceInfo:
        """Return central specific attributes."""
        return self._central.device_information

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes of the base entity."""
        return {}

    @property
    def platform(self) -> HmPlatform:
        """Return the platform."""
        return HmPlatform.HUB_SENSOR

    # pylint: disable=no-self-use
    async def load_data(self) -> None:
        """Do not load data for the hub here."""
        return

    # pylint: disable=no-self-use
    async def fetch_data(self) -> None:
        """fetch data for the hub."""
        return

    def register_update_callback(self, update_callback: Callable) -> None:
        """register update callback"""
        if callable(update_callback) and update_callback not in self._update_callbacks:
            self._update_callbacks.append(update_callback)

    def unregister_update_callback(self, update_callback: Callable) -> None:
        """remove update callback"""
        if update_callback in self._update_callbacks:
            self._update_callbacks.remove(update_callback)

    def update_entity(self, *args: Any) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        for _callback in self._update_callbacks:
            _callback(self.unique_id)

    def register_remove_callback(self, remove_callback: Callable) -> None:
        """register the remove callback"""
        if callable(remove_callback):
            self._remove_callbacks.append(remove_callback)

    def unregister_remove_callback(self, remove_callback: Callable) -> None:
        """remove the remove callback"""
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
        self.last_update = datetime.now()


class HmSystemVariable(BaseHubEntity):
    """Class for a homematic system variable."""

    def __init__(self, central: hm_central.CentralUnit, data: SystemVariableData):
        self._hub: HmHub | None = central.hub
        self._data = data
        unique_id = generate_unique_id(
            central=central,
            address=SYSVAR_ADDRESS,
            parameter=slugify(data.name),
        )
        super().__init__(
            central=central,
            unique_id=unique_id,
            name=f"{central.instance_name}_SV_{data.name}",
        )
        self._unit = data.unit
        self.data_type = data.data_type
        self._value = data.value
        self._value_list = data.value_list
        self.max_value = data.max_value
        self.min_value = data.min_value
        self.internal = data.internal

    @property
    def device_information(self) -> HmDeviceInfo:
        """Return device specific attributes."""
        if self._hub:
            return self._hub.device_information
        return HmDeviceInfo(identifier="NN")

    @property
    def platform(self) -> HmPlatform:
        """Return the platform."""
        if isinstance(self.value, bool):
            return HmPlatform.HUB_BINARY_SENSOR
        return HmPlatform.HUB_SENSOR

    @property
    def value(self) -> Any:
        """Return the value of the entity."""
        return self._value

    @property
    def value_list(self) -> list[str] | None:
        """Return the value list of the entity."""
        return self._value_list

    @property
    def unit(self) -> str | None:
        """Return the unit of the entity."""
        if self._unit:
            return self._unit
        if isinstance(self._value, (int, float)):
            return "#"
        return None

    def update_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if self.data_type:
            value = parse_sys_var(data_type=self.data_type, raw_value=value)
        else:
            old_value = self._value
            if isinstance(old_value, bool):
                value = bool(value)
            elif isinstance(old_value, float):
                value = float(value)
            elif isinstance(old_value, int):
                value = int(value)
            elif isinstance(old_value, str):
                value = str(value)

        if self._value != value:
            self._value = value
            self.update_entity()

    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if (
            self.data_type == SYSVAR_TYPE_LIST
            and isinstance(value, str)
            and self._value_list
            and value in self._value_list
        ):
            await self._central.set_system_variable(
                name=self._data.name, value=self._value_list.index(value)
            )
            return

        await self._central.set_system_variable(
            name=self._data.name, value=parse_sys_var(self.data_type, value)
        )


class HmHub(BaseHubEntity):
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central: hm_central.CentralUnit):
        """Initialize HomeMatic hub."""
        unique_id: str = generate_unique_id(central=central, address=HUB_ADDRESS)
        name: str = central.instance_name
        super().__init__(central, unique_id, name)
        self.hub_entities: dict[str, HmSystemVariable] = {}
        self._variables: dict[str, Any] = {}
        self.should_poll = True
        self._value: int = 0

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._variables.copy()

    @property
    def value(self) -> int:
        """Return the value of the entity."""
        return self._value

    @property
    def hub_entities_by_platform(self) -> dict[HmPlatform, list[HmSystemVariable]]:
        """Return the system variables by platform"""
        sysvars: dict[HmPlatform, list[HmSystemVariable]] = {}
        for entity in self.hub_entities.values():
            if entity.platform not in sysvars:
                sysvars[entity.platform] = []
            sysvars[entity.platform].append(entity)

        return sysvars

    async def fetch_data(self) -> None:
        """fetch data for the hub."""
        if self._central.available:
            await self._update_entities()
            await self._update_hub_state()

    async def _update_hub_state(self) -> None:
        """Retrieve latest service_messages."""
        value = 0
        if self._central.model == BACKEND_CCU:
            service_messages = await self._central.get_system_variable(SERVICE_MESSAGES)
            if service_messages is not None and isinstance(service_messages, float):
                value = int(service_messages)

        if self._value != value:
            self._value = value
            self.update_entity()

    async def _update_entities(self) -> None:
        """Retrieve all variable data and update hmvariable values."""
        self._variables.clear()
        variables = await self._central.get_all_system_variables()
        if not variables:
            _LOGGER.debug(
                "_update_entities: No sysvars received for %s",
                self._central.instance_name,
            )
            return
        _LOGGER.debug(
            "_update_entities: %i sysvars received for %s",
            len(variables),
            self._central.instance_name,
        )

        # remove some variables in case of CCU Backend
        # - OldValue(s) are for internal calculations
        if self._central.model is BACKEND_CCU:
            variables = _clean_variables(variables)

        for sysvar in variables:
            name = sysvar.name
            value = _check_length(name=name, value=sysvar.value)
            if _is_excluded(name, EXCLUDED_FROM_SENSOR):
                self._variables[name] = value
                continue

            entity: HmSystemVariable | None = self.hub_entities.get(name)
            if entity:
                entity.update_value(value)
            else:
                self._create_system_variable(data=sysvar)

        self.update_entity()

    def _create_system_variable(self, data: SystemVariableData) -> None:
        """Create system variable as entity."""
        self.hub_entities[data.name] = HmSystemVariable(
            central=self._central,
            data=data,
        )

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if entity := self.hub_entities.get(name):
            await entity.send_variable(value=value)
        elif name in self.attributes:
            await self._central.set_system_variable(name=name, value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self.name)


def _is_excluded(variable: str, exclude_list: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    for marker in exclude_list:
        if marker in variable:
            return True
    return False


def _check_length(name: str, value: Any) -> Any:
    """Check the lenth of a variable."""
    if isinstance(value, str) and len(value) > 255:
        _LOGGER.warning(
            "Value of sysvar %s exceedes maximum allowed length of 255 chars. Value will be limited to 255 chars.",
            name,
        )
        return value[0:255:1]
    return value


def _clean_variables(variables: list[SystemVariableData]) -> list[SystemVariableData]:
    cleaned_variables: list[SystemVariableData] = []
    for sysvar in variables:
        if _is_excluded(sysvar.name, EXCLUDED):
            continue
        cleaned_variables.append(sysvar)
    return cleaned_variables
