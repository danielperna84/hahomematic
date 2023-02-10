"""Support for entities used within hahomematic."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

from hahomematic.const import INIT_DATETIME
from hahomematic.helpers import updated_within_seconds

G = TypeVar("G")  # think about variance
S = TypeVar("S")


# pylint: disable=invalid-name
class generic_property(Generic[G, S], property):
    """Generic property implementation."""

    fget: Callable[[Any], G] | None
    fset: Callable[[Any, S], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], G] | None = None,
        fset: Callable[[Any, S], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, __fget: Callable[[Any], G]) -> generic_property:
        """Return generic getter."""
        return type(self)(__fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, __fset: Callable[[Any, S], None]) -> generic_property:
        """Return generic setter."""
        return type(self)(self.fget, __fset, self.fdel, self.__doc__)

    def deleter(self, __fdel: Callable[[Any], None]) -> generic_property:
        """Return generic deleter."""
        return type(self)(self.fget, self.fset, __fdel, self.__doc__)

    def __get__(self, __obj: Any, __type: type | None = None) -> G:
        """Return the attribute."""
        if __obj is None:
            return self  # type: ignore[return-value]
        if self.fget is None:
            raise AttributeError("unreadable attribute")  # pragma: no cover
        return self.fget(__obj)

    def __set__(self, __obj: Any, __value: Any) -> None:
        """Set the attribute."""
        if self.fset is None:
            raise AttributeError("can't set attribute")  # pragma: no cover
        self.fset(__obj, __value)

    def __delete__(self, __obj: Any) -> None:
        """Delete the attribute."""
        if self.fdel is None:
            raise AttributeError("can't delete attribute")  # pragma: no cover
        self.fdel(__obj)


# pylint: disable=invalid-name
class config_property(generic_property[G, S], property):
    """Decorate to mark own config properties."""


# pylint: disable=invalid-name
class value_property(generic_property[G, S], property):
    """Decorate to mark own value properties."""


def _get_public_attributes_by_decorator(
    data_object: Any, property_decorator: type
) -> dict[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = [
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_")
        and isinstance(getattr(data_object.__class__, y), property_decorator)
    ]
    return {x: getattr(data_object, x) for x in pub_attributes}


def get_public_attributes_for_config_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=config_property
    )


def get_public_attributes_for_value_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator value_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=value_property
    )


class PayloadMixin:
    """Mixin to add payload methods to class."""

    @property
    def config_payload(self) -> dict[str, Any]:
        """Return the config payload."""
        return get_public_attributes_for_config_property(data_object=self)

    @property
    def value_payload(self) -> dict[str, Any]:
        """Return the value payload."""
        return get_public_attributes_for_value_property(data_object=self)


class OnTimeMixin:
    """Mixin to add on_time support."""

    def __init__(self) -> None:
        """Init OnTimeMixin."""
        self._on_time: float | None = None
        self._on_time_updated: datetime = INIT_DATETIME

    def set_on_time(self, on_time: float) -> None:
        """Set the on_time."""
        self._on_time = on_time
        self._on_time_updated = datetime.now()

    def get_on_time_and_cleanup(self) -> float | None:
        """Return the on_time and cleanup afterwards."""
        if self._on_time is None:
            return None
        # save values
        on_time = self._on_time
        on_time_updated = self._on_time_updated
        # cleanup values
        self._on_time = None
        self._on_time_updated = INIT_DATETIME
        if not updated_within_seconds(last_update=on_time_updated, max_age_seconds=5):
            return None
        return on_time


@dataclass
class CustomConfig:
    """Data for custom entity creation."""

    func: Callable
    channels: tuple[int, ...]
    extended: ExtendedConfig | None = None


@dataclass
class ExtendedConfig:
    """Extended data for custom entity creation."""

    fixed_channels: dict[int, dict[str, str]] | None = None
    additional_entities: dict[int | tuple[int, ...], tuple[str, ...]] | None = None

    @property
    def required_parameters(self) -> tuple[str, ...]:
        """Return vol.Required parameters from extended config."""
        required_parameters: list[str] = []
        if fixed_channels := self.fixed_channels:
            for mapping in fixed_channels.values():
                required_parameters.extend(mapping.values())

        if additional_entities := self.additional_entities:
            for parameters in additional_entities.values():
                required_parameters.extend(parameters)

        return tuple(required_parameters)
