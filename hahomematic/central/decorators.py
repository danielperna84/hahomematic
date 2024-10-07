"""Decorators for central used within hahomematic."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Final, cast

from hahomematic import central as hmcu, client as hmcl
from hahomematic.central import xml_rpc_server as xmlrpc
from hahomematic.const import BackendSystemEvent
from hahomematic.exceptions import HaHomematicException
from hahomematic.support import reduce_args

_LOGGER: Final = logging.getLogger(__name__)
_INTERFACE_ID: Final = "interface_id"


def callback_backend_system(system_event: BackendSystemEvent) -> Callable:
    """Check if backend_system_callback is set and call it AFTER original function."""

    def decorator_backend_system_callback[**_P, _R](
        func: Callable[_P, _R | Awaitable[_R]],
    ) -> Callable[_P, _R | Awaitable[_R]]:
        """Decorate callback system events."""

        @wraps(func)
        async def async_wrapper_backend_system_callback(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap async callback system events."""
            return_value = cast(_R, await func(*args, **kwargs))  # type: ignore[misc]
            await _exec_backend_system_callback(*args, **kwargs)
            return return_value

        @wraps(func)
        def wrapper_backend_system_callback(*args: _P.args, **kwargs: _P.kwargs) -> _R:
            """Wrap callback system events."""
            return_value = cast(_R, func(*args, **kwargs))
            try:
                unit = args[0]
                central: hmcu.CentralUnit | None = None
                if isinstance(unit, hmcu.CentralUnit):
                    central = unit
                if central is None and isinstance(unit, xmlrpc.RPCFunctions):
                    central = unit.get_central(interface_id=str(args[1]))
                if central:
                    central.looper.create_task(
                        _exec_backend_system_callback(*args, **kwargs),
                        name="wrapper_backend_system_callback",
                    )
            except Exception as ex:
                _LOGGER.warning(
                    "EXEC_BACKEND_SYSTEM_CALLBACK failed: Problem with identifying central: %s",
                    reduce_args(args=ex.args),
                )
            return return_value

        async def _exec_backend_system_callback(*args: Any, **kwargs: Any) -> None:
            """Execute the callback for a system event."""

            if not ((len(args) > 1 and not kwargs) or (len(args) == 1 and kwargs)):
                _LOGGER.warning(
                    "EXEC_BACKEND_SYSTEM_CALLBACK failed: *args not supported for callback_system_event"
                )
            try:
                args = args[1:]
                interface_id: str = args[0] if len(args) > 0 else str(kwargs[_INTERFACE_ID])
                if client := hmcl.get_client(interface_id=interface_id):
                    client.modified_at = datetime.now()
                    client.central.fire_backend_system_callback(
                        system_event=system_event, **kwargs
                    )
            except Exception as ex:  # pragma: no cover
                _LOGGER.warning(
                    "EXEC_BACKEND_SYSTEM_CALLBACK failed: Unable to reduce kwargs for backend_system_callback"
                )
                raise HaHomematicException(
                    f"args-exception backend_system_callback [{reduce_args(args=ex.args)}]"
                ) from ex

        if asyncio.iscoroutinefunction(func):
            return async_wrapper_backend_system_callback
        return wrapper_backend_system_callback

    return decorator_backend_system_callback


def callback_event[**_P, _R](
    func: Callable[_P, _R],
) -> Callable:
    """Check if event_callback is set and call it AFTER original function."""

    @wraps(func)
    async def async_wrapper_event_callback(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap callback events."""
        return_value = cast(_R, await func(*args, **kwargs))  # type: ignore[misc]
        _exec_event_callback(*args, **kwargs)
        return return_value

    def _exec_event_callback(*args: Any, **kwargs: Any) -> None:
        """Execute the callback for an entity event."""
        try:
            args = args[1:]
            interface_id: str = args[0] if len(args) > 1 else str(kwargs[_INTERFACE_ID])
            if client := hmcl.get_client(interface_id=interface_id):
                client.modified_at = datetime.now()
                client.central.fire_backend_parameter_callback(*args, **kwargs)
        except Exception as ex:  # pragma: no cover
            _LOGGER.warning(
                "EXEC_ENTITY_EVENT_CALLBACK failed: Unable to reduce kwargs for event_callback"
            )
            raise HaHomematicException(
                f"args-exception event_callback [{reduce_args(args=ex.args)}]"
            ) from ex

    return async_wrapper_event_callback
