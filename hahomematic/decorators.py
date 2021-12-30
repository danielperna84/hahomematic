"""
Decorators used within hahomematic.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import functools
import logging
from typing import Any

import hahomematic.data as hm_data

_LOGGER = logging.getLogger(__name__)


def callback_system_event(name: str) -> Callable:
    """
    Check if callback_system is set and call it AFTER original function.
    """

    def decorator_callback_system_event(func: Callable) -> Callable:
        """Decorator for callback system event."""

        @functools.wraps(func)
        def wrapper_callback_system_event(*args: Any) -> Any:
            """Wrapper for callback system event."""
            return_value = func(*args)
            try:
                # We don't want to pass the function itself
                args = args[1:]
                interface_id = args[0]
                client = hm_data.get_client_by_interface_id(interface_id)
            except Exception as err:
                _LOGGER.warning("Failed to reduce args for callback_system_event.")
                raise Exception("args-exception callback_system_event") from err
            if client:
                client.last_updated = datetime.now()
                if client.central.callback_system_event is not None:
                    client.central.callback_system_event(name, *args)
            return return_value

        return wrapper_callback_system_event

    return decorator_callback_system_event


def callback_event(func: Callable) -> Callable:
    """
    Check if callback_event is set and call it AFTER original function.
    """

    @functools.wraps(func)
    def wrapper_callback_event(*args: Any) -> Any:
        """Wrapper for callback event."""
        return_value = func(*args)
        try:
            # We don't want to pass the function itself
            args = args[1:]
            interface_id = args[0]
            client = hm_data.get_client_by_interface_id(interface_id)
        except Exception as err:
            _LOGGER.warning("Failed to reduce args for callback_event.")
            raise Exception("args-exception callback_event") from err
        if client:
            client.last_updated = datetime.now()
            if client.central.callback_entity_event is not None:
                client.central.callback_entity_event(*args)
        return return_value

    return wrapper_callback_event
