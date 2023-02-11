"""Decorators used within hahomematic."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
from inspect import getfullargspec
import logging
from typing import Any, ParamSpec, TypeVar

from hahomematic import client as hmcl
from hahomematic.exceptions import HaHomematicException
from hahomematic.platforms import entity as hme

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
            collector = hme.CallParameterCollector(client=args[0].device.client)
            kwargs[argument_name] = collector
            return_value = await func(*args, **kwargs)
            await collector.send_data()
        return return_value

    return wrapper_collector  # type: ignore[return-value]
