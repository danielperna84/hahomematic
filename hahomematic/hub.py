"""Module for the hub"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Final

import hahomematic.central_unit as hm_central
from hahomematic.const import (
    BACKEND_CCU,
    HH_EVENT_HUB_CREATED,
    SYSVAR_HM_TYPE_FLOAT,
    SYSVAR_HM_TYPE_INTEGER,
    SYSVAR_TYPE_ALARM,
    SYSVAR_TYPE_LIST,
    SYSVAR_TYPE_LOGIC,
    SYSVAR_TYPE_STRING,
)
from hahomematic.entity import GenericSystemVariable
from hahomematic.generic_platforms.binary_sensor import HmSysvarBinarySensor
from hahomematic.generic_platforms.button import HmProgramButton
from hahomematic.generic_platforms.number import HmSysvarNumber
from hahomematic.generic_platforms.select import HmSysvarSelect
from hahomematic.generic_platforms.sensor import HmSysvarSensor
from hahomematic.generic_platforms.switch import HmSysvarSwitch
from hahomematic.generic_platforms.text import HmSysvarText
from hahomematic.helpers import ProgramData, SystemVariableData

_LOGGER = logging.getLogger(__name__)

EXCLUDED = [
    "OldVal",
    "pcCCUID",
]


class HmHub:
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central: hm_central.CentralUnit):
        """Initialize HomeMatic hub."""
        self._sema_fetch_sysvars = asyncio.Semaphore()
        self._sema_fetch_programs = asyncio.Semaphore()
        self._central: Final[hm_central.CentralUnit] = central
        self.sysvar_entities: Final[dict[str, GenericSystemVariable]] = {}
        self.program_entities: Final[dict[str, HmProgramButton]] = {}

    async def fetch_sysvar_data(self, include_internal: bool = True) -> None:
        """fetch sysvar data for the hub."""
        async with self._sema_fetch_sysvars:
            if self._central.available:
                await self._update_sysvar_entities(include_internal=include_internal)

    async def fetch_program_data(self, include_internal: bool = False) -> None:
        """fetch program data for the hub."""
        async with self._sema_fetch_programs:
            if self._central.available:
                await self._update_program_entities(include_internal=include_internal)

    async def _update_program_entities(self, include_internal: bool) -> None:
        """Retrieve all program data and update program values."""

        programs = await self._central.get_all_programs(
            include_internal=include_internal
        )
        if not programs:
            _LOGGER.debug(
                "_update_program_entities: No programs received for %s",
                self._central.name,
            )
            return
        _LOGGER.debug(
            "_update_entities: %i programs received for %s",
            len(programs),
            self._central.name,
        )

        missing_program_ids = self._identify_missing_program_ids(programs=programs)
        if missing_program_ids:
            self._remove_program_entity(ids=missing_program_ids)

        new_programs: list[HmProgramButton] = []

        for program_data in programs:
            entity: HmProgramButton | None = self.program_entities.get(program_data.pid)
            if entity:
                entity.update_data(data=program_data)
            else:
                new_programs.append(self._create_program(data=program_data))

        if (
            new_programs
            and self._central.callback_system_event is not None
            and callable(self._central.callback_system_event)
        ):
            self._central.callback_system_event(HH_EVENT_HUB_CREATED, new_programs)

    async def _update_sysvar_entities(self, include_internal: bool = True) -> None:
        """Retrieve all variable data and update hmvariable values."""
        variables = await self._central.get_all_system_variables(
            include_internal=include_internal
        )
        if not variables:
            _LOGGER.debug(
                "_update_entities: No sysvars received for %s",
                self._central.name,
            )
            return
        _LOGGER.debug(
            "_update_entities: %i sysvars received for %s",
            len(variables),
            self._central.name,
        )

        # remove some variables in case of CCU Backend
        # - OldValue(s) are for internal calculations
        if self._central.model is BACKEND_CCU:
            variables = _clean_variables(variables)

        missing_variable_names = self._identify_missing_variable_names(
            variables=variables
        )
        if missing_variable_names:
            self._remove_sysvar_entity(del_entities=missing_variable_names)

        new_sysvars: list[GenericSystemVariable] = []

        for sysvar in variables:
            name = sysvar.name
            value = sysvar.value

            entity: GenericSystemVariable | None = self.sysvar_entities.get(name)
            if entity:
                entity.update_value(value)
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if (
            new_sysvars
            and self._central.callback_system_event is not None
            and callable(self._central.callback_system_event)
        ):
            await asyncio.sleep(5)
            self._central.callback_system_event(HH_EVENT_HUB_CREATED, new_sysvars)

    def _create_program(self, data: ProgramData) -> HmProgramButton:
        """Create program as entity."""
        program_entity = HmProgramButton(central=self._central, data=data)
        self.program_entities[data.pid] = program_entity
        return program_entity

    def _create_system_variable(
        self, data: SystemVariableData
    ) -> GenericSystemVariable:
        """Create system variable as entity."""
        sysvar_entity = self._create_sysvar_entity(data=data)
        self.sysvar_entities[data.name] = sysvar_entity
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
            if data_type == SYSVAR_TYPE_STRING and extended_sysvar:
                return HmSysvarText(central=self._central, data=data)

        return HmSysvarSensor(central=self._central, data=data)

    def _remove_program_entity(self, ids: list[str]) -> None:
        """Remove sysvar entity from hub."""
        for pid in ids:
            if pid in self.program_entities:
                entity = self.program_entities[pid]
                entity.remove_entity()
                del self.program_entities[pid]

    def _remove_sysvar_entity(self, del_entities: set[str]) -> None:
        """Remove sysvar entity from hub."""
        for name in del_entities:
            if name in self.sysvar_entities:
                entity = self.sysvar_entities[name]
                entity.remove_entity()
                del self.sysvar_entities[name]

    async def set_system_variable(self, name: str, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if entity := self.sysvar_entities.get(name):
            await entity.send_variable(value=value)
        else:
            _LOGGER.warning("Variable %s not found on %s", name, self._central.name)

    def _identify_missing_program_ids(self, programs: list[ProgramData]) -> list[str]:
        """Identify missing programs."""
        program_ids: list[str] = [x.pid for x in programs]
        missing_programs: list[str] = []
        for pid in self.program_entities:
            if pid not in program_ids:
                missing_programs.append(pid)
        return missing_programs

    def _identify_missing_variable_names(
        self, variables: list[SystemVariableData]
    ) -> set[str]:
        """Identify missing variables."""
        variable_names: dict[str, bool] = {x.name: x.extended_sysvar for x in variables}
        missing_variables: set[str] = set()
        for sysvar_entity in self.sysvar_entities.values():
            if sysvar_entity.data_type == SYSVAR_TYPE_STRING:
                continue
            ccu_name = sysvar_entity.ccu_var_name
            if ccu_name not in variable_names.keys() or (
                sysvar_entity.is_extended is not variable_names.get(ccu_name)
            ):
                missing_variables.add(ccu_name)
        return missing_variables


def _is_excluded(variable: str, excludes: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    for marker in excludes:
        if marker in variable:
            return True
    return False


def _clean_variables(variables: list[SystemVariableData]) -> list[SystemVariableData]:
    """Clean variables by removing excluded."""
    cleaned_variables: list[SystemVariableData] = []
    for sysvar in variables:
        if _is_excluded(sysvar.name, EXCLUDED):
            continue
        cleaned_variables.append(sysvar)
    return cleaned_variables
