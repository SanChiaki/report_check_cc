from dataclasses import dataclass

from report_check.core.concurrency import ExternalApiLimiter
from report_check.models.manager import ModelManager
from report_check.storage.artifacts import ArtifactsManager
from report_check.storage.file import FileStorage
from report_check.storage.task_store import TaskStore
from report_check.worker.cleanup import TaskCleanupManager
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker


@dataclass
class ReportCheckRuntime:
    task_store: TaskStore
    file_storage: FileStorage
    task_queue: TaskQueue
    artifacts_manager: ArtifactsManager
    model_manager: ModelManager
    external_api_limiter: ExternalApiLimiter
    cleanup_manager: TaskCleanupManager
    worker: BackgroundWorker


_runtime: ReportCheckRuntime | None = None


def set_runtime(runtime: ReportCheckRuntime) -> None:
    global _runtime
    _runtime = runtime


def get_runtime() -> ReportCheckRuntime:
    if _runtime is None:
        raise RuntimeError("report_check runtime is not initialized")
    return _runtime


def clear_runtime() -> None:
    global _runtime
    _runtime = None
