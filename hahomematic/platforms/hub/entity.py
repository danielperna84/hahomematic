"""Module for HaHomematic hub platforms."""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, Final

from slugify import slugify

from hahomematic import central_unit as hmcu
from hahomematic.const import SYSVAR_ADDRESS
from hahomematic.platforms.entity import CallbackEntity
from hahomematic.platforms.support import (
    config_property,
    generate_unique_identifier,
    value_property,
)
from hahomematic.support import HubData, SystemVariableData, parse_sys_var


class GenericHubEntity(CallbackEntity):
    """Class for a HomeMatic system variable."""

    def __init__(
        self,
        central: hmcu.CentralUnit,
        address: str,
        data: HubData,
    ) -> None:
        """Initialize the entity."""
        unique_identifier: Final[str] = generate_unique_identifier(
            central=central,
            address=address,
            parameter=slugify(data.name),
        )
        super().__init__(unique_identifier=unique_identifier)
        self.central: Final[hmcu.CentralUnit] = central
        self._attr_name: Final[str] = self.get_name(data=data)
        self._attr_full_name: Final[str] = f"{self.central.name}_{self._attr_name}"

    @abstractmethod
    def get_name(self, data: HubData) -> str:
        """Return the name of the hub entity."""

    @config_property
    def full_name(self) -> str:
        """Return the fullname of the entity."""
        return self._attr_full_name

    @config_property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return self._attr_name


class GenericSystemVariable(GenericHubEntity):
    """Class for a HomeMatic system variable."""

    _attr_is_extended = False

    def __init__(
        self,
        central: hmcu.CentralUnit,
        data: SystemVariableData,
    ) -> None:
        """Initialize the entity."""
        super().__init__(central=central, address=SYSVAR_ADDRESS, data=data)
        self.ccu_var_name: Final[str] = data.name
        self.data_type: Final[str | None] = data.data_type
        self._attr_value_list: Final[tuple[str, ...] | None] = (
            tuple(data.value_list) if data.value_list else None
        )
        self._attr_max: Final[float | int | None] = data.max_value
        self._attr_min: Final[float | int | None] = data.min_value
        self._attr_unit: Final[str | None] = data.unit
        self._attr_value: bool | float | int | str | None = data.value

    @property
    def available(self) -> bool:
        """Return the availability of the device."""
        return self.central.available

    @value_property
    def value(self) -> Any | None:
        """Return the value."""
        return self._attr_value

    @value_property
    def value_list(self) -> tuple[str, ...] | None:
        """Return the value_list."""
        return self._attr_value_list

    @config_property
    def max(self) -> float | int | None:
        """Return the max value."""
        return self._attr_max

    @config_property
    def min(self) -> float | int | None:
        """Return the min value."""
        return self._attr_min

    @config_property
    def unit(self) -> str | None:
        """Return the unit of the entity."""
        return self._attr_unit

    @property
    def is_extended(self) -> bool:
        """Return if the entity is an extended type."""
        return self._attr_is_extended

    def get_name(self, data: HubData) -> str:
        """Return the name of the sysvar entity."""
        if data.name.lower().startswith(tuple({"v_", "sv_"})):
            return data.name.title()
        return f"Sv_{data.name}".title()

    def update_value(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if self.data_type:
            value = parse_sys_var(data_type=self.data_type, raw_value=value)
        else:
            old_value = self._attr_value
            if isinstance(old_value, bool):
                value = bool(value)
            elif isinstance(old_value, int):
                value = int(value)
            elif isinstance(old_value, str):
                value = str(value)
            elif isinstance(old_value, float):
                value = float(value)

        if self._attr_value != value:
            self._attr_value = value
            self.update_entity()

    async def send_variable(self, value: Any) -> None:
        """Set variable value on CCU/Homegear."""
        if client := self.central.get_primary_client():
            await client.set_system_variable(
                name=self.ccu_var_name, value=parse_sys_var(self.data_type, value)
            )
        self.update_value(value=value)
