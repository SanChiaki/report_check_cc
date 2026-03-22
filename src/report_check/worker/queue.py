import asyncio


class TaskQueue:
    """In-memory async task queue."""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, task_id: str):
        await self._queue.put(task_id)

    async def dequeue(self) -> str:
        return await self._queue.get()

    def size(self) -> int:
        return self._queue.qsize()
