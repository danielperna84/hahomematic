"""Decorators for entities used within hahomematic."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import Enum
from typing import Any


# pylint: disable=invalid-name
class generic_property[_GETTER, _SETTER](property):
    """Generic property implementation."""

    fget: Callable[[Any], _GETTER] | None
    fset: Callable[[Any, _SETTER], None] | None
    fdel: Callable[[Any], None] | None

    def __init__(
        self,
        fget: Callable[[Any], _GETTER] | None = None,
        fset: Callable[[Any, _SETTER], None] | None = None,
        fdel: Callable[[Any], None] | None = None,
        doc: str | None = None,
    ) -> None:
        """Init the generic property."""
        super().__init__(fget, fset, fdel, doc)
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, __fget: Callable[[Any], _GETTER]) -> generic_property:
        """Return generic getter."""
        return type(self)(__fget, self.fset, self.fdel, self.__doc__)  # pragma: no cover

    def setter(self, __fset: Callable[[Any, _SETTER], None]) -> generic_property:
        """Return generic setter."""
        return type(self)(self.fget, __fset, self.fdel, self.__doc__)

    def deleter(self, __fdel: Callable[[Any], None]) -> generic_property:
        """Return generic deleter."""
        return type(self)(self.fget, self.fset, __fdel, self.__doc__)

    def __get__(self, __obj: Any, __type: type | None = None) -> _GETTER:
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
class config_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own config properties."""


# pylint: disable=invalid-name
class value_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own value properties."""


def _get_public_attributes_by_decorator(
    data_object: Any, property_decorator: type
) -> Mapping[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = [
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_")
        and isinstance(getattr(data_object.__class__, y), property_decorator)
    ]
    return {x: _get_text_value(getattr(data_object, x)) for x in pub_attributes}


def _get_text_value(value: Any) -> Any:
    """Convert value to text."""
    if isinstance(value, (list, tuple, set)):
        return tuple(_get_text_value(v) for v in value)
    if isinstance(value, Enum):
        return str(value)
    if isinstance(value, datetime):
        return datetime.timestamp(value)
    return value


def get_public_attributes_for_config_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=config_property
    )


def get_public_attributes_for_value_property(data_object: Any) -> Mapping[str, Any]:
    """Return the object attributes by decorator value_property."""
    return _get_public_attributes_by_decorator(
        data_object=data_object, property_decorator=value_property
    )
