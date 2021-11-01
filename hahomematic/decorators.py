"""
Decorators used within hahomematic.
"""

import functools
import logging
import time

from hahomematic.data import get_client_by_interface_id

LOG = logging.getLogger(__name__)


def systemcallback(name):
    """
    Check if systemcallback is set and call it AFTER original function.
    """

    def decorator_systemcallback(func):
        @functools.wraps(func)
        def wrapper_systemcallback(*args):
            return_value = func(*args)
            try:
                # We don't want to pass the function itself
                args = args[1:]
                interface_id = args[0]
                client = get_client_by_interface_id(interface_id)
            # pylint: disable=broad-except
            except Exception as err:
                LOG.warning("Failed to reduce args for systemcallback.")
                raise Exception("args-exception systemcallback") from err
            if client:
                client.initialized = int(time.time())
            if client.server.callback_system_event is not None:
                # pylint: disable=not-callable
                client.server.callback_system_event(name, *args)
            return return_value

        return wrapper_systemcallback

    return decorator_systemcallback


def eventcallback(func):
    """
    Check if eventcallback is set and call it AFTER original function.
    """

    @functools.wraps(func)
    def wrapper_eventcallback(*args):
        return_value = func(*args)
        try:
            # We don't want to pass the function itself
            args = args[1:]
            interface_id = args[0]
            client = get_client_by_interface_id(interface_id)
        # pylint: disable=broad-except
        except Exception as err:
            LOG.warning("Failed to reduce args for eventcallback.")
            raise Exception("args-exception eventcallback") from err
        if client:
            client.initialized = int(time.time())
        if client.server.callback_device_event is not None:
            # pylint: disable=not-callable
            client.server.callback_device_event(*args)
        return return_value

    return wrapper_eventcallback
