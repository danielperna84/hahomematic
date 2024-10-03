"""Send queue for central used within hahomematic."""

from __future__ import annotations

from asyncio import Queue, QueueEmpty
from collections.abc import Callable
import logging
from typing import Final

from hahomematic.async_support import Looper
from hahomematic.exceptions import BaseHomematicException
from hahomematic.support import reduce_args

_LOGGER = logging.getLogger(__name__)


class CommandQueueHandler:
    """Queue handler for sending queued commands."""

    def __init__(self) -> None:
        """Init the SendCommandQueueHandler."""
        self._queues: Final[dict[str, Queue[Callable | None]]] = {}
        self._looper: Final = Looper()

    def empty_queue(self, address: str) -> None:
        """Empty a queue for a device."""
        if queue := self._queues.get(address):
            try:
                while not queue.empty():
                    queue.get_nowait()
                    queue.task_done()
            except QueueEmpty:
                pass

    async def put(self, address: str, command: Callable) -> None:
        """Put command to queue."""
        if address not in self._queues:
            queue: Queue[Callable | None] = Queue()
            self._looper.create_task(_command_consumer(queue), name=f"command consumer-{address}")
            self._queues[address] = queue
        await self._queues[address].put(command)

    async def stop(self) -> None:
        """Add None to queue to stop the consumer."""
        for queue in self._queues.values():
            await queue.put(None)
        await self._looper.block_till_done()


class DeviceQueueHandler:
    """Queue handler for sending queued commands."""

    def __init__(self, address: str) -> None:
        """Init the SendCommandQueueHandler."""
        self._address: Final = address
        self._queue: Queue[Callable | None] | None = None
        self._looper: Final = Looper()

    def empty_queue(self) -> None:
        """Empty a queue for a device."""
        if self._queue:
            try:
                while not self._queue.empty():
                    self._queue.get_nowait()
                    self._queue.task_done()
            except QueueEmpty:
                pass

    async def put(self, command: Callable) -> None:
        """Put command to queue."""
        if not self._queue:
            self._queue = Queue()
            self._looper.create_task(
                _command_consumer(self._queue), name=f"command consumer-{self._address}"
            )
        await self._queue.put(command)

    async def stop(self) -> None:
        """Add None to queue to stop the consumer."""
        if self._queue:
            await self._queue.put(None)
        await self._looper.block_till_done()


async def _command_consumer(queue: Queue) -> None:
    """Consume the commands."""
    # consume work
    while True:
        try:
            if (command := await queue.get()) is None:
                break
            try:
                await command()
            except BaseHomematicException as bhe:
                logging.getLogger(command.func.__module__).warning(
                    "%s with params [%s] failed: %s",
                    command.func.__name__.upper(),
                    f"{command.args} {"/".join([str(kw) for kw in command.keywords.values()])}",
                    reduce_args(args=bhe.args),
                )
            finally:
                queue.task_done()
        except Exception as ex:
            _LOGGER.warning(
                "COMMAND_CONSUMER: command could not be dequeued: %s", reduce_args(args=ex.args)
            )
