"""Send queue for central used within hahomematic."""

from __future__ import annotations

from asyncio import Queue, sleep
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

    async def put(self, device_address: str, command: Callable) -> None:
        """Put send_command to device queue."""
        if device_address not in self._queues:
            device_queue: Queue[Callable | None] = Queue()
            self._looper.create_task(
                _device_consumer(device_queue), name=f"device_consumer-{device_address}"
            )
            self._queues[device_address] = device_queue
        await self._queues[device_address].put(command)
        await sleep(0.1)

    async def stop(self) -> None:
        """Add None to queue to stop the consumer."""
        for queue in self._queues.values():
            await queue.put(None)
        await self._looper.block_till_done()


async def _device_consumer(queue: Queue) -> None:
    """Consume the device commands."""
    # consume work
    while True:
        try:
            if (command := await queue.get()) is None:
                break
            await command()
            queue.task_done()
        except Exception as ex:
            _LOGGER.debug(
                "DEVICE_CONSUMER: Unable do deque command: %s", reduce_args(args=ex.args)
            )
