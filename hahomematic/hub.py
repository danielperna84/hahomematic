"""Module for the hub"""
from __future__ import annotations

import logging
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.config import EXTENDED_SYSVARS
from hahomematic.const import (
    BACKEND_CCU,
    HUB_ADDRESS,
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
    HmEntityUsage,
    HmPlatform,
)
from hahomematic.entity import CallbackEntity, GenericSystemVariable
from hahomematic.helpers import HmDeviceInfo, SystemVariableData, generate_unique_id
from hahomematic.platforms.binary_sensor import HmSysvarBinarySensor
from hahomematic.platforms.number import HmSysvarNumber
from hahomematic.platforms.select import HmSysvarSelect
from hahomematic.platforms.sensor import HmSysvarSensor
from hahomematic.platforms.switch import HmSysvarSwitch

_LOGGER = logging.getLogger(__name__)

EXCLUDED_FROM_SENSOR = [
    "pcCCUID",
]

EXCLUDED = [
    "OldVal",
]

SERVICE_MESSAGES = "Servicemeldungen"


class HmHub(CallbackEntity):
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central: hm_central.CentralUnit):
        """Initialize HomeMatic hub."""
        CallbackEntity.__init__(self)
        self._central = central
        self.unique_id: str = generate_unique_id(central=central, address=HUB_ADDRESS)
        self.name: str = central.instance_name
        self.hub_entities: dict[str, GenericSystemVariable] = {}
        self._variables: dict[str, Any] = {}
        self.should_poll = True
        self._value: int = 0
        self.create_in_ha: bool = True
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
        """Return the state attributes."""
        return self._variables.copy()

    @property
    def platform(self) -> HmPlatform:
        """Return the platform."""
        return HmPlatform.HUB_SENSOR

    @property
    def value(self) -> int:
        """Return the value of the entity."""
        return self._value

    @property
    def hub_entities_by_platform(self) -> dict[HmPlatform, list[GenericSystemVariable]]:
        """Return the system variables by platform"""
        sysvars: dict[HmPlatform, list[GenericSystemVariable]] = {}
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

            entity: GenericSystemVariable | None = self.hub_entities.get(name)
            if entity:
                entity.update_value(value)
            else:
                self._create_system_variable(data=sysvar)

        self.update_entity()

    def _create_system_variable(self, data: SystemVariableData) -> None:
        """Create system variable as entity."""
        self.hub_entities[data.name] = self._create_sysvar_entity(data=data)

    def _create_sysvar_entity(self, data: SystemVariableData) -> GenericSystemVariable:
        data_type = data.data_type
        internal = data.internal
        if data_type:
            if data_type in (SYSVAR_TYPE_ALARM, SYSVAR_TYPE_LOGIC):
                if EXTENDED_SYSVARS and internal is False:
                    return HmSysvarSwitch(central=self._central, data=data)
                return HmSysvarBinarySensor(central=self._central, data=data)
            if data_type == SYSVAR_TYPE_LIST:
                if EXTENDED_SYSVARS and internal is False:
                    return HmSysvarSelect(central=self._central, data=data)
                return HmSysvarSensor(central=self._central, data=data)
            if data_type in (SYSVAR_HM_TYPE_FLOAT, SYSVAR_HM_TYPE_INTEGER):
                if EXTENDED_SYSVARS and internal is False:
                    return HmSysvarNumber(central=self._central, data=data)
                return HmSysvarSensor(central=self._central, data=data)
        if isinstance(self.value, bool):
            return HmSysvarBinarySensor(central=self._central, data=data)
        return HmSysvarSensor(central=self._central, data=data)

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if entity := self.hub_entities.get(name):
            await entity.send_variable(value=value)
        elif name in self.attributes:
            await self._central.set_system_variable(name=name, value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self.name)

    # pylint: disable=no-self-use
    async def load_data(self) -> None:
        """Do not load data for the hub here."""
        return

    def update_entity(self, *args: Any) -> None:
        """
        Do what is needed when the state of the entity has been updated.
        """
        self._set_last_update()
        super().update_entity(*args)

    def remove_entity(self, *args: Any) -> None:
        """
        Do what is needed when the entity has been removed.
        """
        self._set_last_update()
        super().remove_entity(*args)


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
