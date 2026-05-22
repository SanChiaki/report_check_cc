from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportCheckSettings:
    upload_path: str = "data/uploads"
    artifacts_path: str = "data/tasks"
    max_waiting_tasks: int = 10
    worker_concurrency: int = 1
    per_task_rule_concurrency: int = 1
    completed_task_retention_seconds: float = 300
    default_provider: str = "openai"
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    external_api_limits: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(
        cls,
        app_config: dict[str, Any] | None = None,
        model_config: dict[str, Any] | None = None,
    ) -> "ReportCheckSettings":
        app_config = app_config or {}
        model_config = model_config or {}

        storage = app_config.get("storage", {})
        execution = app_config.get("execution", {})

        return cls(
            upload_path=storage.get("upload_path", cls.upload_path),
            artifacts_path=storage.get("artifacts_path", cls.artifacts_path),
            max_waiting_tasks=execution.get("max_waiting_tasks", cls.max_waiting_tasks),
            worker_concurrency=execution.get("worker_concurrency", cls.worker_concurrency),
            per_task_rule_concurrency=execution.get(
                "per_task_rule_concurrency", cls.per_task_rule_concurrency
            ),
            completed_task_retention_seconds=execution.get(
                "completed_task_retention_seconds",
                cls.completed_task_retention_seconds,
            ),
            default_provider=model_config.get("default_provider", cls.default_provider),
            providers=model_config.get("providers", {}),
            external_api_limits=app_config.get("external_api_limits", {}),
        )
