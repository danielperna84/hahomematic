"""Decorators for central used within hahomematic."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Final, ParamSpec, TypeVar, cast

from hahomematic import client as hmcl
from hahomematic.const import SystemEvent
from hahomematic.exceptions import HaHomematicException
from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)
_CallableT = TypeVar("_CallableT", bound=Callable[..., Any])
_P = ParamSpec("_P")
_R = TypeVar("_R")

_INTERFACE_ID: Final = "interface_id"


def callback_system_event(system_event: SystemEvent) -> Callable:
    """Check if callback_system is set and call it AFTER original function."""

    def decorator_callback_system_event(
        func: Callable[_P, _R | Awaitable[_R]],
    ) -> Callable[_P, _R | Awaitable[_R]]:
        """Decorate callback system events."""

        @wraps(func)
        async def async_wrapper_callback_system_event(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap async callback system events."""
            return_value = cast(_R, await func(*args, **kwargs))  # type: ignore[misc]
            _exec_callback_system_event(*args, **kwargs)
            return return_value

        @wraps(func)
        def wrapper_callback_system_event(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap callback system events."""
            return_value = cast(_R, func(*args, **kwargs))
            _exec_callback_system_event(*args, **kwargs)
            return return_value

        def _exec_callback_system_event(*args: Any, **kwargs: Any) -> None:
            """Execute the callback for a system event."""
            if len(args) > 1:
                _LOGGER.warning(
                    "EXEC_CALLBACK_SYSTEM_EVENT failed: *args not supported for callback_system_event"
                )
            try:
                args = args[1:]
                interface_id: str = args[0] if len(args) > 1 else str(kwargs[_INTERFACE_ID])
                if client := hmcl.get_client(interface_id=interface_id):
                    client.last_updated = datetime.now()
                    client.central.fire_system_event_callback(system_event=system_event, **kwargs)
            except Exception as err:  # pragma: no cover
                _LOGGER.warning(
                    "EXEC_CALLBACK_SYSTEM_EVENT failed: Unable to reduce kwargs for callback_system_event"
                )
                raise HaHomematicException(
                    f"args-exception callback_system_event [{reduce_args(args=err.args)}]"
                ) from err

        if asyncio.iscoroutinefunction(func):
            return async_wrapper_callback_system_event
        return wrapper_callback_system_event

    return decorator_callback_system_event


def callback_event(func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Check if callback_event is set and call it AFTER original function."""

    @wraps(func)
    def wrapper_callback_event(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap callback events."""
        return_value = func(*args, **kwargs)
        _exec_callback_entity_event(*args, **kwargs)
        return return_value

    def _exec_callback_entity_event(*args: Any, **kwargs: Any) -> None:
        """Execute the callback for an entity event."""
        try:
            args = args[1:]
            interface_id: str = args[0] if len(args) > 1 else str(kwargs[_INTERFACE_ID])
            if client := hmcl.get_client(interface_id=interface_id):
                client.last_updated = datetime.now()
                client.central.fire_entity_event_callback(*args, **kwargs)
        except Exception as err:  # pragma: no cover
            _LOGGER.warning(
                "EXEC_CALLBACK_ENTITY_EVENT failed: Unable to reduce kwargs for callback_event"
            )
            raise HaHomematicException(
                f"args-exception callback_event [{reduce_args(args=err.args)}]"
            ) from err

    return wrapper_callback_event
