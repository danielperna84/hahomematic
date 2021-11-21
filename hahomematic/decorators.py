"""
Decorators used within hahomematic.
"""

import functools
import logging
import time

from hahomematic.data import get_client_by_interface_id

_LOGGER = logging.getLogger(__name__)


def callback_system_event(name):
    """
    Check if callback_system is set and call it AFTER original function.
    """

    def decorator_callback_system_event(func):
        @functools.wraps(func)
        def wrapper_callback_system_event(*args):
            return_value = func(*args)
            try:
                # We don't want to pass the function itself
                args = args[1:]
                interface_id = args[0]
                client = get_client_by_interface_id(interface_id)
            except Exception as err:
                _LOGGER.warning("Failed to reduce args for callback_system_event.")
                raise Exception("args-exception callback_system_event") from err
            if client:
                client.time_initialized = int(time.time())
            if client.central.callback_system_event is not None:
                client.central.callback_system_event(name, *args)
            return return_value

        return wrapper_callback_system_event

    return decorator_callback_system_event


def callback_event(func):
    """
    Check if callback_event is set and call it AFTER original function.
    """

    @functools.wraps(func)
    def wrapper_callback_event(*args):
        return_value = func(*args)
        try:
            # We don't want to pass the function itself
            args = args[1:]
            interface_id = args[0]
            client = get_client_by_interface_id(interface_id)
        except Exception as err:
            _LOGGER.warning("Failed to reduce args for callback_event.")
            raise Exception("args-exception callback_event") from err
        if client:
            client.time_initialized = int(time.time())
        if client.central.callback_entity_event is not None:
            client.central.callback_entity_event(*args)
        return return_value

    return wrapper_callback_event
