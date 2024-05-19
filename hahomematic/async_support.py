"""Module with support for loop interaction."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Collection, Coroutine
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures._base import CancelledError
from functools import wraps
import logging
from time import monotonic
from typing import Any, Final, cast

from hahomematic.const import BLOCK_LOG_TIMEOUT
from hahomematic.exceptions import HaHomematicException
from hahomematic.support import debug_enabled, reduce_args

_LOGGER: Final = logging.getLogger(__name__)


class Looper:
    """Helper class for event loop support."""

    def __init__(self) -> None:
        """Init the loop helper."""
        self._tasks: Final[set[asyncio.Future[Any]]] = set()
        self._loop = asyncio.get_event_loop()

    async def block_till_done(self) -> None:
        """Code from HA. Block until all pending work is done."""
        # To flush out any call_soon_threadsafe
        await asyncio.sleep(0)
        start_time: float | None = None
        current_task = asyncio.current_task()
        while tasks := [
            task for task in self._tasks if task is not current_task and not cancelling(task)
        ]:
            await self._await_and_log_pending(tasks)

            if start_time is None:
                # Avoid calling monotonic() until we know
                # we may need to start logging blocked tasks.
                start_time = 0
            elif start_time == 0:
                # If we have waited twice then we set the start
                # time
                start_time = monotonic()
            elif monotonic() - start_time > BLOCK_LOG_TIMEOUT:
                # We have waited at least three loops and new tasks
                # continue to block. At this point we start
                # logging all waiting tasks.
                for task in tasks:
                    _LOGGER.debug("Waiting for task: %s", task)

    async def _await_and_log_pending(self, pending: Collection[asyncio.Future[Any]]) -> None:
        """Code from HA. Await and log tasks that take a long time."""
        wait_time = 0
        while pending:
            _, pending = await asyncio.wait(pending, timeout=BLOCK_LOG_TIMEOUT)
            if not pending:
                return
            wait_time += BLOCK_LOG_TIMEOUT
            for task in pending:
                _LOGGER.debug("Waited %s seconds for task: %s", wait_time, task)

    def create_task(self, target: Coroutine[Any, Any, Any], name: str) -> None:
        """Add task to the executor pool."""
        try:
            self._loop.call_soon_threadsafe(self._async_create_task, target, name)
        except CancelledError:
            _LOGGER.debug(
                "create_task: task cancelled for %s",
                name,
            )
            return

    def _async_create_task[_R](
        self, target: Coroutine[Any, Any, _R], name: str
    ) -> asyncio.Task[_R]:
        """Create a task from within the event_loop. This method must be run in the event_loop."""
        task = self._loop.create_task(target, name=name)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.remove)
        return task

    def run_coroutine(self, coro: Coroutine, name: str) -> Any:
        """Call coroutine from sync."""
        try:
            return asyncio.run_coroutine_threadsafe(coro, self._loop).result()
        except CancelledError:  # pragma: no cover
            _LOGGER.debug(
                "run_coroutine: coroutine interrupted for %s",
                name,
            )
            return None

    def async_add_executor_job[_T](
        self,
        target: Callable[..., _T],
        *args: Any,
        name: str,
        executor: ThreadPoolExecutor | None = None,
    ) -> asyncio.Future[_T]:
        """Add an executor job from within the event_loop."""
        try:
            task = self._loop.run_in_executor(executor, target, *args)
            self._tasks.add(task)
            task.add_done_callback(self._tasks.remove)
        except (TimeoutError, CancelledError) as err:  # pragma: no cover
            message = (
                f"async_add_executor_job: task cancelled for {name} [{reduce_args(args=err.args)}]"
            )
            _LOGGER.debug(message)
            raise HaHomematicException(message) from err
        return task


def cancelling(task: asyncio.Future[Any]) -> bool:
    """Return True if task is cancelling."""
    return bool((cancelling_ := getattr(task, "cancelling", None)) and cancelling_())


def loop_check[**_P, _R](func: Callable[_P, _R]) -> Callable[_P, _R]:
    """Annotation to mark method that must be run within the event loop."""

    _with_loop: set = set()

    @wraps(func)
    def wrapper_loop_check(*args: _P.args, **kwargs: _P.kwargs) -> _R:
        """Wrap loop check."""
        return_value = func(*args, **kwargs)

        try:
            asyncio.get_running_loop()
            loop_running = True
        except Exception:
            loop_running = False

        if not loop_running and func not in _with_loop:
            _with_loop.add(func)
            _LOGGER.warning(
                "Method %s must run in the event_loop. No loop detected.", func.__name__
            )

        return return_value

    setattr(func, "_loop_check", True)
    return cast(Callable[_P, _R], wrapper_loop_check) if debug_enabled() else func
