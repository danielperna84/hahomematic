"""Decorators used within hahomematic."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime
from functools import wraps
import logging
from typing import Any, Final

_LOGGER: Final = logging.getLogger(__name__)


def measure_execution_time[_CallableT: Callable[..., Any]](func: _CallableT) -> _CallableT:
    """Decorate function to measure the function execution time."""

    is_enabled = _LOGGER.isEnabledFor(level=logging.DEBUG)

    @wraps(func)
    async def async_measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""
        if is_enabled:
            start = datetime.now()
        try:
            return await func(*args, **kwargs)
        finally:
            if is_enabled:
                delta = (datetime.now() - start).total_seconds()
                arg = str(args[0]) if len(args) > 0 else ""
                _LOGGER.info(
                    "Execution of %s took %ss (%s)",
                    func.__name__,
                    delta,
                    arg,
                )

    @wraps(func)
    def measure_wrapper(*args: Any, **kwargs: Any) -> Any:
        """Wrap method."""
        if is_enabled:
            start = datetime.now()
        try:
            return func(*args, **kwargs)
        finally:
            if is_enabled:
                delta = (datetime.now() - start).total_seconds()
                _LOGGER.info(
                    "Execution of %s took %ss args(%s) kwargs(%s) ",
                    func.__name__,
                    delta,
                    args,
                    kwargs,
                )

    if asyncio.iscoroutinefunction(func):
        return async_measure_wrapper  # type: ignore[return-value]
    return measure_wrapper  # type: ignore[return-value]
