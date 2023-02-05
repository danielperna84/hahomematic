"""Decorators used within hahomematic."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
from inspect import getfullargspec
import logging
from typing import Any, Generic, ParamSpec, TypeVar

import hahomematic.client as hmcl
import hahomematic.entity as hme
from hahomematic.exceptions import HaHomematicException

_LOGGER = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def callback_system_event(name: str) -> Callable:
    """Check if callback_system is set and call it AFTER original function."""

    def decorator_callback_system_event(func: Callable[P, R]) -> Callable[P, R]:
        """Decorate callback system events."""

        @wraps(func)
        def wrapper_callback_system_event(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap callback system events."""
            return_value = func(*args, **kwargs)
            _exec_callback_system_event(name, *args, **kwargs)
            return return_value

        return wrapper_callback_system_event

    return decorator_callback_system_event


def async_callback_system_event(name: str) -> Callable:
    """Check if callback_system is set and call it AFTER original function."""

    def async_decorator_callback_system_event(
        func: Callable[P, Awaitable[R]]
    ) -> Callable[P, Awaitable[R]]:
        """Decorate callback system events."""

        @wraps(func)
        async def async_wrapper_callback_system_event(*args: P.args, **kwargs: P.kwargs) -> R:
            """Wrap async callback system events."""
            return_value = await func(*args, **kwargs)
            _exec_callback_system_event(name, *args, **kwargs)
            return return_value

        return async_wrapper_callback_system_event

    return async_decorator_callback_system_event


def _exec_callback_system_event(name: str, *args: Any, **kwargs: Any) -> None:
    """Execute the callback for a system event."""
    if len(args) > 1:
        _LOGGER.warning(
            "EXEC_CALLBACK_SYSTEM_EVENT failed: *args not supported for callback_system_event"
        )
    try:
        args = args[1:]
        interface_id: str = args[0] if len(args) > 1 else str(kwargs["interface_id"])
        client = hmcl.get_client(interface_id=interface_id)
    except Exception as err:  # pragma: no cover
        _LOGGER.warning(
            "EXEC_CALLBACK_SYSTEM_EVENT failed: Unable to reduce kwargs for callback_system_event"
        )
        raise HaHomematicException("args-exception callback_system_event") from err
    if client:
        client.last_updated = datetime.now()
        if client.central.callback_system_event is not None:
            client.central.callback_system_event(name, **kwargs)


def callback_event(func: Callable[P, R]) -> Callable[P, R]:
    """Check if callback_event is set and call it AFTER original function."""

    @wraps(func)
    def wrapper_callback_event(*args: P.args, **kwargs: P.kwargs) -> R:
        """Wrap callback events."""
        return_value = func(*args, **kwargs)
        _exec_callback_entity_event(*args, **kwargs)
        return return_value

    def _exec_callback_entity_event(*args: Any, **kwargs: Any) -> None:
        """Execute the callback for an entity event."""
        try:
            args = args[1:]
            interface_id: str = args[0] if len(args) > 1 else str(kwargs["interface_id"])
            client = hmcl.get_client(interface_id=interface_id)
        except Exception as err:  # pragma: no cover
            _LOGGER.warning(
                "EXEC_CALLBACK_ENTITY_EVENT failed: Unable to reduce kwargs for callback_event"
            )
            raise HaHomematicException("args-exception callback_event") from err
        if client:
            client.last_updated = datetime.now()
            if client.central.callback_entity_event is not None:
                client.central.callback_entity_event(*args, **kwargs)

    return wrapper_callback_event


_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])


def bind_collector(func: _CallableT) -> _CallableT:
    """Decorate function to automatically add collector if not set."""
    argument_name = "collector"
    argument_index = getfullargspec(func).args.index(argument_name)

    @wraps(func)
    async def wrapper_collector(*args: Any, **kwargs: Any) -> Any:
        """Wrap method to add collector."""
        try:
            collector_exists = args[argument_index] is not None
        except IndexError:
            collector_exists = kwargs.get(argument_name) is not None

        if collector_exists:
            return_value = await func(*args, **kwargs)
        else:
            collector = hme.CallParameterCollector(custom_entity=args[0])
            kwargs[argument_name] = collector
            return_value = await func(*args, **kwargs)
            await collector.send_data()
        return return_value

    return wrapper_collector  # type: ignore[return-value]


G = TypeVar("G")  # think about variance
S = TypeVar("S")


# pylint: disable=invalid-name
class generic_property(Generic[G, S], property):
    """Generic property implemantation."""

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
