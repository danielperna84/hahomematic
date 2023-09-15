"""Decorators for entities used within hahomematic."""
from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from inspect import getfullargspec
from typing import Any, TypeVar

from hahomematic.platforms import entity as hme

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
