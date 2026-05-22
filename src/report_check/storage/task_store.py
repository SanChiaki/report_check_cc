import asyncio
from copy import deepcopy
from datetime import datetime
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class TaskStore:
    """In-memory task state store for queue-driven execution."""

    def __init__(self):
        self._tasks: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        task_id: str,
        file_name: str,
        file_path: str,
        rules: dict,
        report_type: str | None = None,
        context_vars: dict | None = None,
        extra_file_paths: list[str] | None = None,
    ) -> str:
        task = {
            "task_id": task_id,
            "file_name": file_name,
            "file_path": file_path,
            "extra_files": list(extra_file_paths or []),
            "rules": deepcopy(rules),
            "report_type": report_type,
            "context_vars": deepcopy(context_vars) if context_vars is not None else None,
            "status": TaskStatus.PENDING.value,
            "progress": 0,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "error": None,
            "check_results": [],
        }
        async with self._lock:
            self._tasks[task_id] = task
        return task_id

    async def get_task(self, task_id: str) -> dict | None:
        async with self._lock:
            task = self._tasks.get(task_id)
            return deepcopy(task) if task is not None else None

    async def delete_task(self, task_id: str):
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def update_task_status(self, task_id: str, status: TaskStatus, error: str | None = None):
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            task["status"] = status.value
            if status == TaskStatus.PROCESSING:
                task["started_at"] = datetime.now().isoformat()
            elif status == TaskStatus.COMPLETED:
                task["completed_at"] = datetime.now().isoformat()
                task["progress"] = 100
                task["error"] = None
            elif status == TaskStatus.FAILED:
                task["completed_at"] = datetime.now().isoformat()
                task["error"] = error
            else:
                task["error"] = error

    async def update_task_progress(self, task_id: str, progress: int):
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task["progress"] = progress

    async def save_check_results(self, task_id: str, results: list[dict]):
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return
            task["check_results"] = deepcopy(results)

    async def get_check_results(self, task_id: str) -> list[dict]:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return []
            return deepcopy(task.get("check_results", []))

    async def count(self) -> int:
        async with self._lock:
            return len(self._tasks)
