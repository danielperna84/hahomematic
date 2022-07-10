"""Module for the hub"""
from __future__ import annotations

import logging
from typing import Any

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    BACKEND_CCU,
    HH_EVENT_SYSVARS_CREATED,
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
        self._unique_id: str = generate_unique_id(central=central, address=HUB_ADDRESS)
        self._name: str = central.instance_name
        self.syvar_entities: dict[str, GenericSystemVariable] = {}
        self._hub_attributes: dict[str, Any] = {}
        self.should_poll = True
        self._value: int | None = None
        self.create_in_ha: bool = True
        self.usage = HmEntityUsage.ENTITY

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self._central.available

    @property
    def attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self._hub_attributes.copy()

    @property
    def device_information(self) -> HmDeviceInfo:
        """Return central specific attributes."""
        return self._central.device_information

    @property
    def name(self) -> str:
        """Return the hub name."""
        return self._name

    @property
    def platform(self) -> HmPlatform:
        """Return the platform."""
        return HmPlatform.HUB_SENSOR

    @property
    def unique_id(self) -> str:
        """Return the hub unique_id."""
        return self._unique_id

    @property
    def value(self) -> int | None:
        """Return the value of the entity."""
        return self._value

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
        self._hub_attributes.clear()
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

        missing_variable_names = self._identify_missing_variable_names(
            variables=variables
        )
        if missing_variable_names:
            self._remove_sysvar_entity(names=missing_variable_names)

        new_sysvars: list[GenericSystemVariable] = []

        for sysvar in variables:
            name = sysvar.name
            value = sysvar.value
            if _is_excluded(name, EXCLUDED_FROM_SENSOR):
                self._hub_attributes[name] = value
                continue

            entity: GenericSystemVariable | None = self.syvar_entities.get(name)
            if entity:
                entity.update_value(value)
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if (
            new_sysvars
            and self._central.callback_system_event is not None
            and callable(self._central.callback_system_event)
        ):
            self._central.callback_system_event(HH_EVENT_SYSVARS_CREATED, new_sysvars)

    def _create_system_variable(
        self, data: SystemVariableData
    ) -> GenericSystemVariable:
        """Create system variable as entity."""
        sysvar_entity = self._create_sysvar_entity(data=data)
        self.syvar_entities[data.name] = sysvar_entity
        return sysvar_entity

    def _create_sysvar_entity(self, data: SystemVariableData) -> GenericSystemVariable:
        """Create sysvar entity."""
        data_type = data.data_type
        extended_sysvar = data.extended_sysvar
        if data_type:
            if data_type in (SYSVAR_TYPE_ALARM, SYSVAR_TYPE_LOGIC):
                if extended_sysvar:
                    return HmSysvarSwitch(central=self._central, data=data)
                return HmSysvarBinarySensor(central=self._central, data=data)
            if data_type == SYSVAR_TYPE_LIST and extended_sysvar:
                return HmSysvarSelect(central=self._central, data=data)
            if (
                data_type in (SYSVAR_HM_TYPE_FLOAT, SYSVAR_HM_TYPE_INTEGER)
                and extended_sysvar
            ):
                return HmSysvarNumber(central=self._central, data=data)
        else:
            if isinstance(self.value, bool):
                return HmSysvarBinarySensor(central=self._central, data=data)
        return HmSysvarSensor(central=self._central, data=data)

    def _remove_sysvar_entity(self, names: list[str]) -> None:
        """Remove sysvar entity from hub."""
        for name in names:
            if name in self._hub_attributes:
                del self._hub_attributes[name]

            if name in self.syvar_entities:
                entity = self.syvar_entities[name]
                entity.remove_entity()
                del self.syvar_entities[name]
        self.update_entity()

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if entity := self.syvar_entities.get(name):
            await entity.send_variable(value=value)
        elif name in self.attributes:
            await self._central.set_system_variable(name=name, value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self._name)

    def _identify_missing_variable_names(
        self, variables: list[SystemVariableData]
    ) -> list[str]:
        """Identify missing variables."""
        variable_names: list[str] = [x.name for x in variables]
        missing_variables: list[str] = []
        for name in self._hub_attributes:
            if name not in variable_names:
                missing_variables.append(name)
        for name in self.syvar_entities:
            if name not in variable_names:
                missing_variables.append(name)
        return missing_variables


def _is_excluded(variable: str, exclude_list: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    for marker in exclude_list:
        if marker in variable:
            return True
    return False


def _clean_variables(variables: list[SystemVariableData]) -> list[SystemVariableData]:
    "Clean variables by removing excluded."
    cleaned_variables: list[SystemVariableData] = []
    for sysvar in variables:
        if _is_excluded(sysvar.name, EXCLUDED):
            continue
        cleaned_variables.append(sysvar)
    return cleaned_variables
