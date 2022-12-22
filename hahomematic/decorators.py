"""
Decorators used within hahomematic.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Generic, TypeVar

import hahomematic.client as hm_client
from hahomematic.exceptions import HaHomematicException

_LOGGER = logging.getLogger(__name__)


def callback_system_event(name: str) -> Callable:
    """
    Check if callback_system is set and call it AFTER original function.
    """

    def decorator_callback_system_event(func: Callable) -> Callable:
        """Decorator for callback system event."""

        @wraps(func)
        async def async_wrapper_callback_system_event(*args: Any) -> Any:
            """Wrapper for callback system event."""
            return_value = await func(*args)
            exec_callback_system_event(*args)
            return return_value

        @wraps(func)
        def wrapper_callback_system_event(*args: Any) -> Any:
            """Wrapper for callback system event."""
            return_value = func(*args)
            exec_callback_system_event(*args)
            return return_value

        def exec_callback_system_event(*args: Any) -> None:
            """Execute the callback for a system event."""
            try:
                # We don't want to pass the function itself
                args = args[1:]
                interface_id = args[0]
                client = hm_client.get_client_by_interface_id(interface_id=interface_id)
            except Exception as err:
                _LOGGER.warning(
                    "exec_callback_system_event failed: "
                    "Unable to reduce args for callback_system_event."
                )
                raise HaHomematicException(
                    "args-exception callback_system_event"
                ) from err
            if client:
                client.last_updated = datetime.now()
                if client.central.callback_system_event is not None:
                    client.central.callback_system_event(name, *args)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper_callback_system_event
        return wrapper_callback_system_event

    return decorator_callback_system_event


def callback_event(func: Callable) -> Callable:
    """
    Check if callback_event is set and call it AFTER original function.
    """

    @wraps(func)
    async def async_wrapper_callback_event(*args: Any) -> Any:
        """Wrapper for callback event."""
        return_value = await func(*args)
        exec_callback_entity_event(*args)
        return return_value

    @wraps(func)
    def wrapper_callback_event(*args: Any) -> Any:
        """Wrapper for callback event."""
        return_value = func(*args)
        exec_callback_entity_event(*args)
        return return_value

    def exec_callback_entity_event(*args: Any) -> None:
        """Execute the callback for an entity event."""
        try:
            # We don't want to pass the function itself
            args = args[1:]
            interface_id = args[0]
            client = hm_client.get_client_by_interface_id(interface_id=interface_id)
        except Exception as err:
            _LOGGER.warning(
                "exec_callback_entity_event failed: "
                "Unable to reduce args for callback_event."
            )
            raise HaHomematicException("args-exception callback_event") from err
        if client:
            client.last_updated = datetime.now()
            if client.central.callback_entity_event is not None:
                client.central.callback_entity_event(*args)

    if asyncio.iscoroutinefunction(func):
        return async_wrapper_callback_event
    return wrapper_callback_event


G = TypeVar("G")  # think about variance
S = TypeVar("S")


# pylint: disable=invalid-name
class generic_property(Generic[G, S], property):
    """Generic property implemantation"""

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
        super().__init__(fget, fset, fdel, doc)
        # self.fget = fget
        # self.fset = fset
        # self.fdel = fdel
        if doc is None and fget is not None:
            doc = fget.__doc__
        self.__doc__ = doc

    def getter(self, __fget: Callable[[Any], G]) -> generic_property:
        """custom generic getter"""
        return type(self)(__fget, self.fset, self.fdel, self.__doc__)

    def setter(self, __fset: Callable[[Any, S], None]) -> generic_property:
        """custom generic setter"""
        return type(self)(self.fget, __fset, self.fdel, self.__doc__)

    def deleter(self, __fdel: Callable[[Any], None]) -> generic_property:
        """custom generic deleter"""
        return type(self)(self.fget, self.fset, __fdel, self.__doc__)

    def __get__(self, __obj: Any, __type: type | None = None) -> G:
        if __obj is None:
            return self  # type: ignore[return-value]
        if self.fget is None:
            raise AttributeError("unreadable attribute")
        return self.fget(__obj)

    def __set__(self, __obj: Any, __value: Any) -> None:
        if self.fset is None:
            raise AttributeError("can't set attribute")
        self.fset(__obj, __value)

    def __delete__(self, __obj: Any) -> None:
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(__obj)


# pylint: disable=invalid-name
class config_property(generic_property[G, S], property):
    """Decorator to mark own config properties."""


# pylint: disable=invalid-name
class value_property(generic_property[G, S], property):
    """Decorator to mark own value properties."""


def _get_public_attributes_by_decorator(
    data_object: Any, property_decorator: type
) -> dict[str, Any]:
    """Return the object attributes by decorator."""
    pub_attributes = list(
        y
        for y in dir(data_object.__class__)
        if not y.startswith("_")
        and isinstance(getattr(data_object.__class__, y), property_decorator)
    )
    return dict((x, getattr(data_object, x)) for x in pub_attributes)


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
