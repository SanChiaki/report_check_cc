import json
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from report_check.main import app, set_standalone_settings_loader
from report_check.settings import ReportCheckSettings
from report_check.worker.queue import TaskQueue


@pytest.fixture(autouse=True)
def reset_loader():
    set_standalone_settings_loader(None)
    yield
    set_standalone_settings_loader(None)


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("VISION_API_KEY", "test-key")
    monkeypatch.setenv("VISION_API_BASE_URL", "https://example.com/v1")

    settings = ReportCheckSettings(
        upload_path=str(tmp_path / "uploads"),
        artifacts_path=str(tmp_path / "tasks"),
        default_provider="openai",
        providers={
            "openai": {
                "text_api_key": "test-key",
                "text_base_url": "https://example.com/v1",
                "multimodal_api_key": "test-key",
                "multimodal_base_url": "https://example.com/v1",
                "text_model": "fake-text",
                "multimodal_model": "fake-mm",
            }
        },
    )
    set_standalone_settings_loader(lambda: settings)

    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "queue_size" in data
        assert "running_tasks" in data
        assert "model_inflight" in data
        assert "model_text_inflight" in data
        assert "model_multimodal_inflight" in data
        assert "version" in data

    def test_lifespan_loads_concurrency_config_into_runtime(self, monkeypatch, tmp_path):
        async def fake_worker_start(self):
            return None

        async def fake_worker_stop(self):
            return None

        monkeypatch.setattr("report_check.bootstrap.BackgroundWorker.start", fake_worker_start)
        monkeypatch.setattr("report_check.bootstrap.BackgroundWorker.stop", fake_worker_stop)

        settings = ReportCheckSettings(
            upload_path=str(tmp_path / "uploads"),
            artifacts_path=str(tmp_path / "tasks"),
            max_waiting_tasks=2,
            worker_concurrency=4,
            per_task_rule_concurrency=6,
            default_provider="fake",
            providers={
                "fake": {
                    "text_api_key": "ignored",
                    "text_base_url": "https://example.com/v1",
                    "multimodal_api_key": "ignored",
                    "multimodal_base_url": "https://example.com/v1",
                    "max_concurrency": 7,
                    "text_max_concurrency": 3,
                    "multimodal_max_concurrency": 2,
                }
            },
            external_api_limits={
                "default_max_concurrency": 3,
                "by_endpoint": {"inventory-api": 1},
            },
        )
        set_standalone_settings_loader(lambda: settings)

        with TestClient(app) as client:
            runtime = client.app.state.report_check_runtime
            queue = runtime.task_queue
            assert queue.try_enqueue("t1") is True
            assert queue.try_enqueue("t2") is True
            assert queue.try_enqueue("t3") is False

            worker = runtime.worker
            assert worker.worker_concurrency == 4
            assert worker.per_task_rule_concurrency == 6

            limiter = runtime.external_api_limiter
            assert limiter._default_state.semaphore is not None
            assert limiter._default_state.semaphore._value == 3
            assert "inventory-api" in limiter._endpoint_states
            assert limiter._endpoint_states["inventory-api"].semaphore is not None
            assert limiter._endpoint_states["inventory-api"].semaphore._value == 1

            model_state = runtime.model_manager._provider_states["fake"]
            assert model_state.total_semaphore is not None
            assert model_state.total_semaphore._value == 7
            assert model_state.text_semaphore is not None
            assert model_state.text_semaphore._value == 3
            assert model_state.multimodal_semaphore is not None
            assert model_state.multimodal_semaphore._value == 2


class TestSubmitEndpoint:
    def test_submit_valid(self, client, sample_excel_path):
        rules = json.dumps(
            {
                "rules": [
                    {"id": "r1", "name": "test", "type": "text", "config": {"keywords": ["交付"]}}
                ]
            }
        )
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files=[("files", ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
                data={"rules": rules},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "message" in data

    def test_submit_invalid_extension(self, client):
        resp = client.post(
            "/api/v1/check/submit",
            files=[("files", ("test.txt", BytesIO(b"hello"), "text/plain"))],
            data={"rules": "{}"},
        )
        assert resp.status_code == 400

    def test_submit_invalid_rules(self, client, sample_excel_path):
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files=[("files", ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
                data={"rules": "not json"},
            )
        assert resp.status_code == 400

    def test_submit_returns_429_when_waiting_queue_is_full(self, client, sample_excel_path):
        runtime = client.app.state.report_check_runtime
        runtime.task_queue = TaskQueue(maxsize=1)
        runtime.task_queue._queue.put_nowait("queued-task")

        upload_root = runtime.file_storage.base_path
        before_task_count = self._count_tasks(runtime.task_store)
        before_upload_dirs = self._count_upload_dirs(upload_root)

        rules = json.dumps(
            {
                "rules": [
                    {"id": "r1", "name": "test", "type": "text", "config": {"keywords": ["交付"]}}
                ]
            }
        )
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files=[("files", ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
                data={"rules": rules},
            )

        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "30"
        assert self._count_tasks(runtime.task_store) == before_task_count
        assert self._count_upload_dirs(upload_root) == before_upload_dirs

    def _count_tasks(self, task_store) -> int:
        return len(task_store._tasks)

    def _count_upload_dirs(self, upload_root: Path) -> int:
        if not upload_root.exists():
            return 0
        return sum(1 for path in upload_root.iterdir() if path.is_dir())


class TestResultEndpoint:
    def test_result_not_found(self, client):
        resp = client.get("/api/v1/check/result/nonexistent-task-id")
        assert resp.status_code == 404


class TestValidateEndpoint:
    def test_validate_valid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1", "name": "t", "type": "text", "config": {"keywords": ["x"]}}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
