"""Support classes used by hahomematic custom entities."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from hahomematic.const import Parameter
from hahomematic.platforms.custom.const import Field


@dataclass(frozen=True, kw_only=True, slots=True)
class CustomConfig:
    """Data for custom entity creation."""

    make_ce_func: Callable
    channels: tuple[int | None, ...] = (1,)
    extended: ExtendedConfig | None = None


@dataclass(frozen=True, kw_only=True, slots=True)
class ExtendedConfig:
    """Extended data for custom entity creation."""

    fixed_channels: Mapping[int, Mapping[Field, Parameter]] | None = None
    additional_entities: Mapping[int | tuple[int, ...], tuple[Parameter, ...]] | None = None

    @property
    def required_parameters(self) -> tuple[Parameter, ...]:
        """Return vol.Required parameters from extended config."""
        required_parameters: list[Parameter] = []
        if fixed_channels := self.fixed_channels:
            for mapping in fixed_channels.values():
                required_parameters.extend(mapping.values())

        if additional_entities := self.additional_entities:
            for parameters in additional_entities.values():
                required_parameters.extend(parameters)

        return tuple(required_parameters)
