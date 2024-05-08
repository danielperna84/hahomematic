"""Send queue for central used within hahomematic."""

from __future__ import annotations

from asyncio import Queue, QueueEmpty, sleep
from collections.abc import Callable
import logging
from typing import Final

from hahomematic.async_support import Looper
from hahomematic.support import reduce_args

_LOGGER = logging.getLogger(__name__)


class CommandQueueHandler:
    """Queue handler for sending queued commands."""

    def __init__(self) -> None:
        """Init the SendCommandQueueHandler."""
        self._queues: Final[dict[str, Queue[Callable | None]]] = {}
        self._exit = False
        self._looper = Looper()

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
        await sleep(0.1)

    async def stop(self) -> None:
        """Add None to queue to stop the consumer."""
        for queue in self._queues.values():
            await queue.put(None)
        await self._looper.block_till_done()


async def _command_consumer(queue: Queue) -> None:
    """Consume the commands."""
    # consume work
    while True:
        try:
            if (command := await queue.get()) is None:
                break
            await command()
            queue.task_done()
        except Exception as ex:
            _LOGGER.debug(
                "COMMAND_CONSUMER: Unable do deque command: %s", reduce_args(args=ex.args)
            )
