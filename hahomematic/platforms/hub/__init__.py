"""Module for HaHomematic hub platforms."""

from __future__ import annotations

import asyncio
from collections.abc import Collection, Mapping, Set as AbstractSet
import logging
from typing import Final

from hahomematic import central as hmcu
from hahomematic.const import (
    HUB_PLATFORMS,
    Backend,
    BackendSystemEvent,
    HmPlatform,
    ProgramData,
    SystemVariableData,
    SysvarType,
)
from hahomematic.platforms.hub.binary_sensor import HmSysvarBinarySensor
from hahomematic.platforms.hub.button import HmProgramButton
from hahomematic.platforms.hub.entity import GenericHubEntity, GenericSystemVariable
from hahomematic.platforms.hub.number import HmSysvarNumber
from hahomematic.platforms.hub.select import HmSysvarSelect
from hahomematic.platforms.hub.sensor import HmSysvarSensor
from hahomematic.platforms.hub.switch import HmSysvarSwitch
from hahomematic.platforms.hub.text import HmSysvarText

__all__ = [
    "GenericHubEntity",
    "GenericSystemVariable",
    "HmProgramButton",
    "HmSysvarBinarySensor",
    "HmSysvarNumber",
    "HmSysvarSelect",
    "HmSysvarSensor",
    "HmSysvarSwitch",
    "HmSysvarText",
    "Hub",
]

_LOGGER: Final = logging.getLogger(__name__)

_EXCLUDED: Final = [
    "OldVal",
    "pcCCUID",
]


class Hub:
    """The HomeMatic hub. (CCU/HomeGear)."""

    def __init__(self, central: hmcu.CentralUnit) -> None:
        """Initialize HomeMatic hub."""
        self._sema_fetch_sysvars: Final = asyncio.Semaphore()
        self._sema_fetch_programs: Final = asyncio.Semaphore()
        self._central: Final = central
        self._config: Final = central.config

    async def fetch_sysvar_data(self, scheduled: bool) -> None:
        """Fetch sysvar data for the hub."""
        if self._config.sysvar_scan_enabled:
            _LOGGER.debug(
                "FETCH_SYSVAR_DATA: % fetching of system variables for %s",
                "Scheduled" if scheduled else "Manual",
                self._central.name,
            )
            async with self._sema_fetch_sysvars:
                if self._central.available:
                    await self._update_sysvar_entities()

    async def fetch_program_data(self, scheduled: bool) -> None:
        """Fetch program data for the hub."""
        if self._config.program_scan_enabled:
            _LOGGER.debug(
                "FETCH_PROGRAM_DATA: % fetching of programs for %s",
                "Scheduled" if scheduled else "Manual",
                self._central.name,
            )
            async with self._sema_fetch_programs:
                if self._central.available:
                    await self._update_program_entities()

    async def _update_program_entities(self) -> None:
        """Retrieve all program data and update program values."""
        programs: tuple[ProgramData, ...] = ()
        if client := self._central.primary_client:
            programs = await client.get_all_programs(
                include_internal=self._config.include_internal_programs
            )
        if not programs:
            _LOGGER.debug(
                "UPDATE_PROGRAM_ENTITIES: No programs received for %s",
                self._central.name,
            )
            return
        _LOGGER.debug(
            "UPDATE_PROGRAM_ENTITIES: %i programs received for %s",
            len(programs),
            self._central.name,
        )

        if missing_program_ids := self._identify_missing_program_ids(programs=programs):
            self._remove_program_entity(ids=missing_program_ids)

        new_programs: list[HmProgramButton] = []

        for program_data in programs:
            if entity := self._central.get_program_button(pid=program_data.pid):
                entity.update_data(data=program_data)
            else:
                new_programs.append(self._create_program(data=program_data))

        if new_programs:
            self._central.fire_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_hub_entities=_get_new_hub_entities(entities=new_programs),
            )

    async def _update_sysvar_entities(self) -> None:
        """Retrieve all variable data and update hmvariable values."""
        variables: tuple[SystemVariableData, ...] = ()
        if client := self._central.primary_client:
            variables = await client.get_all_system_variables(
                include_internal=self._config.include_internal_sysvars
            )
        if not variables:
            _LOGGER.debug(
                "UPDATE_SYSVAR_ENTITIES: No sysvars received for %s",
                self._central.name,
            )
            return
        _LOGGER.debug(
            "UPDATE_SYSVAR_ENTITIES: %i sysvars received for %s",
            len(variables),
            self._central.name,
        )

        # remove some variables in case of CCU Backend
        # - OldValue(s) are for internal calculations
        if self._central.model is Backend.CCU:
            variables = _clean_variables(variables)

        if missing_variable_names := self._identify_missing_variable_names(variables=variables):
            self._remove_sysvar_entity(del_entities=missing_variable_names)

        new_sysvars: list[GenericSystemVariable] = []

        for sysvar in variables:
            name = sysvar.name
            value = sysvar.value

            if entity := self._central.get_sysvar_entity(name=name):
                entity.write_value(value)
            else:
                new_sysvars.append(self._create_system_variable(data=sysvar))

        if new_sysvars:
            self._central.fire_backend_system_callback(
                system_event=BackendSystemEvent.HUB_REFRESHED,
                new_hub_entities=_get_new_hub_entities(entities=new_sysvars),
            )

    def _create_program(self, data: ProgramData) -> HmProgramButton:
        """Create program as entity."""
        program_button = HmProgramButton(central=self._central, data=data)
        self._central.add_program_button(program_button=program_button)
        return program_button

    def _create_system_variable(self, data: SystemVariableData) -> GenericSystemVariable:
        """Create system variable as entity."""
        sysvar_entity = self._create_sysvar_entity(data=data)
        self._central.add_sysvar_entity(sysvar_entity=sysvar_entity)
        return sysvar_entity

    def _create_sysvar_entity(self, data: SystemVariableData) -> GenericSystemVariable:
        """Create sysvar entity."""
        data_type = data.data_type
        extended_sysvar = data.extended_sysvar
        if data_type:
            if data_type in (SysvarType.ALARM, SysvarType.LOGIC):
                if extended_sysvar:
                    return HmSysvarSwitch(central=self._central, data=data)
                return HmSysvarBinarySensor(central=self._central, data=data)
            if data_type == SysvarType.LIST and extended_sysvar:
                return HmSysvarSelect(central=self._central, data=data)
            if data_type in (SysvarType.FLOAT, SysvarType.INTEGER) and extended_sysvar:
                return HmSysvarNumber(central=self._central, data=data)
            if data_type == SysvarType.STRING and extended_sysvar:
                return HmSysvarText(central=self._central, data=data)

        return HmSysvarSensor(central=self._central, data=data)

    def _remove_program_entity(self, ids: tuple[str, ...]) -> None:
        """Remove sysvar entity from hub."""
        for pid in ids:
            self._central.remove_program_button(pid=pid)

    def _remove_sysvar_entity(self, del_entities: tuple[str, ...]) -> None:
        """Remove sysvar entity from hub."""
        for name in del_entities:
            self._central.remove_sysvar_entity(name=name)

    def _identify_missing_program_ids(self, programs: tuple[ProgramData, ...]) -> tuple[str, ...]:
        """Identify missing programs."""
        return tuple(
            program_button.pid
            for program_button in self._central.program_buttons
            if program_button.pid not in [x.pid for x in programs]
        )

    def _identify_missing_variable_names(
        self, variables: tuple[SystemVariableData, ...]
    ) -> tuple[str, ...]:
        """Identify missing variables."""
        variable_names: dict[str, bool] = {x.name: x.extended_sysvar for x in variables}
        missing_variables: list[str] = []
        for sysvar_entity in self._central.sysvar_entities:
            if sysvar_entity.data_type == SysvarType.STRING:
                continue
            ccu_name = sysvar_entity.ccu_var_name
            if ccu_name not in variable_names or (
                sysvar_entity.is_extended is not variable_names.get(ccu_name)
            ):
                missing_variables.append(ccu_name)
        return tuple(missing_variables)


def _is_excluded(variable: str, excludes: list[str]) -> bool:
    """Check if variable is excluded by exclude_list."""
    return any(marker in variable for marker in excludes)


def _clean_variables(variables: tuple[SystemVariableData, ...]) -> tuple[SystemVariableData, ...]:
    """Clean variables by removing excluded."""
    return tuple(sv for sv in variables if not _is_excluded(sv.name, _EXCLUDED))


def _get_new_hub_entities(
    entities: Collection[GenericHubEntity],
) -> Mapping[HmPlatform, AbstractSet[GenericHubEntity]]:
    """Return entities as platform dict."""
    hm_hub_entities: dict[HmPlatform, set[GenericHubEntity]] = {}
    for hm_hub_platform in HUB_PLATFORMS:
        hm_hub_entities[hm_hub_platform] = set()

    for hub_entity in entities:
        if hub_entity.is_registered is False:
            hm_hub_entities[hub_entity.platform].add(hub_entity)

    return hm_hub_entities
