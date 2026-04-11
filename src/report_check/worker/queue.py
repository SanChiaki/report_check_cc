import asyncio


class TaskQueue:
    """In-memory async task queue."""

    def __init__(self, maxsize: int = 0):
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=maxsize)

    async def enqueue(self, task_id: str):
        await self._queue.put(task_id)

    def try_enqueue(self, task_id: str) -> bool:
        try:
            self._queue.put_nowait(task_id)
        except asyncio.QueueFull:
            return False
        return True

    async def dequeue(self) -> str:
        return await self._queue.get()

    def size(self) -> int:
        return self._queue.qsize()
