import asyncio
import logging

from report_check.storage.artifacts import ArtifactsManager
from report_check.storage.file import FileStorage
from report_check.storage.task_store import TaskStore

logger = logging.getLogger(__name__)


class TaskCleanupManager:
    """Remove completed task state and files after a retention window."""

    def __init__(
        self,
        task_store: TaskStore,
        file_storage: FileStorage,
        artifacts_manager: ArtifactsManager,
        retention_seconds: float = 300,
    ):
        self.task_store = task_store
        self.file_storage = file_storage
        self.artifacts_manager = artifacts_manager
        self.retention_seconds = max(float(retention_seconds), 0.0)
        self._tasks: dict[str, asyncio.Task] = {}

    def schedule_cleanup(self, task_id: str) -> None:
        existing = self._tasks.pop(task_id, None)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(self._cleanup_after_delay(task_id))
        self._tasks[task_id] = task
        task.add_done_callback(lambda done_task, tid=task_id: self._tasks.pop(tid, None))

    async def cleanup_now(self, task_id: str) -> None:
        try:
            await self.file_storage.cleanup_task_files(task_id)
            self.artifacts_manager.cleanup_task_artifacts(task_id)
            await self.task_store.delete_task(task_id)
            logger.info("Cleaned up task data for %s", task_id)
        except Exception:
            logger.exception("Failed to clean up task data for %s", task_id)

    async def shutdown(self) -> None:
        pending = [task for task in self._tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        self._tasks.clear()

    async def _cleanup_after_delay(self, task_id: str) -> None:
        try:
            if self.retention_seconds > 0:
                await asyncio.sleep(self.retention_seconds)
            await self.cleanup_now(task_id)
        except asyncio.CancelledError:
            raise
