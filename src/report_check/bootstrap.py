from __future__ import annotations

from pathlib import Path

from report_check.core.concurrency import ExternalApiLimiter
from report_check.models.manager import ModelManager
from report_check.models.openai_adapter import OpenAIAdapter
from report_check.runtime import ReportCheckRuntime, clear_runtime, get_runtime, set_runtime
from report_check.settings import ReportCheckSettings
from report_check.storage.artifacts import ArtifactsManager
from report_check.storage.file import FileStorage
from report_check.storage.task_store import TaskStore
from report_check.worker.cleanup import TaskCleanupManager
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker


def create_runtime(settings: ReportCheckSettings) -> ReportCheckRuntime:
    task_store = TaskStore()
    file_storage = FileStorage(settings.upload_path)
    task_queue = TaskQueue(maxsize=settings.max_waiting_tasks)

    artifacts_path = Path(settings.artifacts_path)
    artifacts_path.mkdir(parents=True, exist_ok=True)
    artifacts_manager = ArtifactsManager(str(artifacts_path))

    model_manager = ModelManager(default_provider=settings.default_provider)

    from report_check.models import fetchers  # noqa: F401

    for name, cfg in settings.providers.items():
        model_manager.register_adapter(name, OpenAIAdapter(cfg))

    external_api_limits = settings.external_api_limits or {}
    external_api_limiter = ExternalApiLimiter(
        default_max_concurrency=external_api_limits.get("default_max_concurrency"),
        by_endpoint=external_api_limits.get("by_endpoint", {}),
    )

    cleanup_manager = TaskCleanupManager(
        task_store=task_store,
        file_storage=file_storage,
        artifacts_manager=artifacts_manager,
        retention_seconds=settings.completed_task_retention_seconds,
    )

    worker = BackgroundWorker(
        task_store=task_store,
        model_manager=model_manager,
        task_queue=task_queue,
        artifacts_manager=artifacts_manager,
        worker_concurrency=settings.worker_concurrency,
        per_task_rule_concurrency=settings.per_task_rule_concurrency,
        external_api_limiter=external_api_limiter,
        cleanup_manager=cleanup_manager,
    )

    return ReportCheckRuntime(
        task_store=task_store,
        file_storage=file_storage,
        task_queue=task_queue,
        artifacts_manager=artifacts_manager,
        model_manager=model_manager,
        external_api_limiter=external_api_limiter,
        cleanup_manager=cleanup_manager,
        worker=worker,
    )


async def init_report_check(settings: ReportCheckSettings) -> ReportCheckRuntime:
    runtime = create_runtime(settings)
    set_runtime(runtime)
    await runtime.worker.start()
    return runtime


async def shutdown_report_check() -> None:
    try:
        runtime = get_runtime()
    except RuntimeError:
        return

    for adapter in runtime.model_manager._adapters.values():
        if hasattr(adapter, "close"):
            await adapter.close()

    await runtime.worker.stop()
    await runtime.cleanup_manager.shutdown()
    clear_runtime()
