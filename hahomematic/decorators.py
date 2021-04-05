"""
Decorators used within hahomematic.
"""

import time
import functools
import logging

from hahomematic import config, data

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
            # pylint: disable=broad-except
            except Exception as err:
                LOG.warning("Failed to reduce args for systemcallback.")
                raise Exception("args-exception systemcallback") from err
            if interface_id in data.CLIENTS:
                data.CLIENTS[interface_id].initialized = int(time.time())
            if config.SYSTEMCALLBACK is not None:
                # pylint: disable=not-callable
                config.SYSTEMCALLBACK(name, *args)
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
        # pylint: disable=broad-except
        except Exception as err:
            LOG.warning("Failed to reduce args for eventcallback.")
            raise Exception("args-exception eventcallback") from err
        if interface_id in data.CLIENTS:
            data.CLIENTS[interface_id].initialized = int(time.time())
        if config.EVENTCALLBACK is not None:
            # pylint: disable=not-callable
            config.EVENTCALLBACK(*args)
        return return_value
    return wrapper_eventcallback
