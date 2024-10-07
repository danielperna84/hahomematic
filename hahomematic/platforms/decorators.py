"""Decorators for entities used within hahomematic."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import Token
from datetime import datetime
from enum import Enum
from functools import wraps
import logging
from typing import Any, ParamSpec, TypeVar

from hahomematic.context import IN_SERVICE_VAR
from hahomematic.exceptions import BaseHomematicException
from hahomematic.support import reduce_args

__all__ = [
    "config_property",
    "get_public_attributes_for_config_property",
    "get_public_attributes_for_info_property",
    "get_public_attributes_for_state_property",
    "get_service_calls",
    "info_property",
    "service",
    "state_property",
]

P = ParamSpec("P")
T = TypeVar("T")


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
class info_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own info properties."""


# pylint: disable=invalid-name
class state_property[_GETTER, _SETTER](generic_property[_GETTER, _SETTER]):
    """Decorate to mark own value properties."""


def _get_public_attributes_by_class_decorator(
    data_object: Any, class_decorator: type
) -> dict[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = [
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_") and isinstance(getattr(data_object.__class__, y), class_decorator)
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


def get_public_attributes_for_config_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator config_property."""
    return _get_public_attributes_by_class_decorator(
        data_object=data_object, class_decorator=config_property
    )


def get_public_attributes_for_info_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator info_property."""
    return _get_public_attributes_by_class_decorator(
        data_object=data_object, class_decorator=info_property
    )


def get_public_attributes_for_state_property(data_object: Any) -> dict[str, Any]:
    """Return the object attributes by decorator state_property."""
    return _get_public_attributes_by_class_decorator(
        data_object=data_object, class_decorator=state_property
    )


def service(log_level: int = logging.ERROR) -> Callable:
    """Mark function as service call and log exceptions."""

    def service_decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        """Decorate service."""

        @wraps(func)
        async def service_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            """Wrap service to log exception."""
            token: Token | None = None
            if not IN_SERVICE_VAR.get():
                token = IN_SERVICE_VAR.set(True)
            try:
                return_value = await func(*args, **kwargs)
                if token:
                    IN_SERVICE_VAR.reset(token)
                return return_value  # noqa: TRY300
            except BaseHomematicException as bhe:
                if token:
                    IN_SERVICE_VAR.reset(token)
                if not IN_SERVICE_VAR.get() and log_level > logging.NOTSET:
                    logging.getLogger(args[0].__module__).log(
                        level=log_level, msg=reduce_args(args=bhe.args)
                    )
                raise

        setattr(service_wrapper, "ha_service", True)
        return service_wrapper

    return service_decorator


def get_service_calls(obj: object) -> dict[str, Callable]:
    """Get all methods decorated with the "bind_collector" or "service_call"  decorator."""
    return {
        name: getattr(obj, name)
        for name in dir(obj)
        if not name.startswith("_")
        and callable(getattr(obj, name))
        and hasattr(getattr(obj, name), "ha_service")
    }
