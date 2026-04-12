import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from report_check.checkers.base import CheckResult
from report_check.checkers.factory import CheckerFactory
from report_check.storage.database import Database, TaskStatus
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker
from report_check.models.manager import ModelManager


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def task_queue() -> TaskQueue:
    return TaskQueue()


class TestTaskQueue:
    @pytest.mark.asyncio
    async def test_try_enqueue_rejects_when_queue_is_full(self):
        queue = TaskQueue(maxsize=1)

        assert queue.try_enqueue("t1") is True
        assert queue.size() == 1
        assert queue.try_enqueue("t2") is False
        assert queue.size() == 1


class TestBackgroundWorker:
    @pytest.mark.asyncio
    async def test_start_creates_multiple_worker_loops(self, db, task_queue):
        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(
            db=db,
            model_manager=mm,
            task_queue=task_queue,
            worker_concurrency=2,
        )

        await worker.start()
        try:
            assert len(worker._workers) == 2
            assert all(not task.done() for task in worker._workers)
        finally:
            await worker.stop()

    @pytest.mark.asyncio
    async def test_multiple_workers_process_queue_concurrently(self, db, task_queue):
        await task_queue.enqueue("t1")
        await task_queue.enqueue("t2")

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(
            db=db,
            model_manager=mm,
            task_queue=task_queue,
            worker_concurrency=2,
        )

        started: set[str] = set()
        both_started = asyncio.Event()
        release = asyncio.Event()

        async def fake_process(task_id: str):
            started.add(task_id)
            if len(started) == 2:
                both_started.set()
            await release.wait()

        worker._process_task = fake_process  # type: ignore[method-assign]

        await worker.start()
        try:
            await asyncio.wait_for(both_started.wait(), timeout=1)
        finally:
            release.set()
            await worker.stop()

        assert started == {"t1", "t2"}

    @pytest.mark.asyncio
    async def test_process_task_runs_rules_concurrently_and_preserves_result_order(
        self,
        db,
        task_queue,
        sample_excel_path,
        monkeypatch,
    ):
        rules = {
            "rules": [
                {"id": "r1", "name": "first", "type": "text", "config": {"delay": 0.05, "message": "first"}},
                {"id": "r2", "name": "second", "type": "text", "config": {"delay": 0.0, "message": "second"}},
                {"id": "r3", "name": "third", "type": "text", "config": {"delay": 0.01, "message": "third"}},
            ]
        }
        await db.create_task(
            task_id="t-concurrent",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )

        inflight = 0
        max_inflight = 0
        inflight_lock = asyncio.Lock()

        class FakeChecker:
            async def check(self, rule_config):
                nonlocal inflight, max_inflight
                async with inflight_lock:
                    inflight += 1
                    max_inflight = max(max_inflight, inflight)
                await asyncio.sleep(rule_config["delay"])
                async with inflight_lock:
                    inflight -= 1
                return CheckResult(status="passed", message=rule_config["message"])

        monkeypatch.setattr(
            CheckerFactory,
            "create",
            lambda *args, **kwargs: FakeChecker(),
        )

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(
            db=db,
            model_manager=mm,
            task_queue=task_queue,
            per_task_rule_concurrency=2,
        )
        await worker._process_task("t-concurrent")

        results = await db.get_check_results("t-concurrent")
        assert max_inflight == 2
        assert [result["message"] for result in results] == ["first", "second", "third"]

    @pytest.mark.asyncio
    async def test_rule_exception_becomes_error_result_without_failing_task(
        self,
        db,
        task_queue,
        sample_excel_path,
        monkeypatch,
    ):
        rules = {
            "rules": [
                {"id": "r1", "name": "boom", "type": "text", "config": {"raise_error": True}},
                {"id": "r2", "name": "ok", "type": "text", "config": {"message": "ok"}},
            ]
        }
        await db.create_task(
            task_id="t-rule-error",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )

        class FakeChecker:
            async def check(self, rule_config):
                if rule_config.get("raise_error"):
                    raise RuntimeError("boom")
                return CheckResult(status="passed", message=rule_config["message"])

        monkeypatch.setattr(
            CheckerFactory,
            "create",
            lambda *args, **kwargs: FakeChecker(),
        )

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(
            db=db,
            model_manager=mm,
            task_queue=task_queue,
            per_task_rule_concurrency=2,
        )
        await worker._process_task("t-rule-error")

        task = await db.get_task("t-rule-error")
        results = await db.get_check_results("t-rule-error")

        assert task["status"] == "completed"
        assert [result["status"] for result in results] == ["error", "passed"]

    @pytest.mark.asyncio
    async def test_process_task_offloads_parse_work_to_thread(
        self,
        db,
        task_queue,
        sample_excel_path,
        monkeypatch,
    ):
        rules = {
            "rules": [
                {"id": "r1", "name": "check keyword", "type": "text",
                 "config": {"keywords": ["交付内容"], "match_mode": "any"}}
            ]
        }
        await db.create_task(
            task_id="t-thread",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )

        to_thread_calls = []
        real_to_thread = asyncio.to_thread

        async def recording_to_thread(func, *args, **kwargs):
            to_thread_calls.append(getattr(func, "__name__", repr(func)))
            return await real_to_thread(func, *args, **kwargs)

        monkeypatch.setattr("report_check.worker.worker.asyncio.to_thread", recording_to_thread)

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)
        await worker._process_task("t-thread")

        assert to_thread_calls

    @pytest.mark.asyncio
    async def test_process_task_reuses_rendered_pages_across_concurrent_render_rules(
        self,
        db,
        task_queue,
        sample_excel_path,
        monkeypatch,
    ):
        rules = {
            "rules": [
                {
                    "id": "r1",
                    "name": "multimodal",
                    "type": "multimodal_check",
                    "config": {"requirement": "检查报告整体是否完整"},
                },
                {
                    "id": "r2",
                    "name": "image consistency",
                    "type": "image_consistency",
                    "config": {"requirement": "检查项的配图是否符合描述"},
                },
            ]
        }
        await db.create_task(
            task_id="t-render-cache",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )

        render_calls = 0

        async def fake_render(self, report_data, artifacts=None):
            nonlocal render_calls
            render_calls += 1
            await asyncio.sleep(0.05)
            return [b"page-image"]

        async def fake_call_multimodal_model(prompt: str, image: bytes, **kwargs):
            if "质检报告审核专家" in prompt:
                return json.dumps({"check_items": []})
            return json.dumps({"status": "passed", "message": "ok", "confidence": 0.9})

        monkeypatch.setattr("report_check.parser.renderer.ReportRenderer.render", fake_render)

        mm = MagicMock()
        mm.call_multimodal_model = AsyncMock(side_effect=fake_call_multimodal_model)
        worker = BackgroundWorker(
            db=db,
            model_manager=mm,
            task_queue=task_queue,
            per_task_rule_concurrency=2,
        )
        await worker._process_task("t-render-cache")

        task = await db.get_task("t-render-cache")
        results = await db.get_check_results("t-render-cache")

        assert task["status"] == "completed"
        assert len(results) == 2
        assert render_calls == 1

    @pytest.mark.asyncio
    async def test_process_text_check_task(self, db, task_queue, sample_excel_path):
        """End-to-end: enqueue a task with text rule, process, verify results."""
        rules = {
            "rules": [
                {"id": "r1", "name": "check keyword", "type": "text",
                 "config": {"keywords": ["交付内容"], "match_mode": "any"}}
            ]
        }
        await db.create_task(
            task_id="t1",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )
        await task_queue.enqueue("t1")

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)
        # Process one task directly
        await worker._process_task("t1")

        task = await db.get_task("t1")
        assert task["status"] == "completed"

        results = await db.get_check_results("t1")
        assert len(results) == 1
        assert results[0]["status"] == "passed"

    @pytest.mark.asyncio
    async def test_process_task_invalid_file_fails(self, db, task_queue, tmp_path):
        """Task with nonexistent file should fail gracefully."""
        rules = {"rules": [{"id": "r1", "name": "t", "type": "text", "config": {"keywords": ["x"]}}]}
        await db.create_task(
            task_id="t2",
            file_name="missing.xlsx",
            file_path=str(tmp_path / "missing.xlsx"),
            rules=rules,
        )

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)
        await worker._process_task("t2")

        task = await db.get_task("t2")
        assert task["status"] == "failed"
        assert task["error"] is not None

    @pytest.mark.asyncio
    async def test_crash_recovery(self, db, task_queue, sample_excel_path):
        """Processing tasks should be re-enqueued on startup."""
        rules = {"rules": []}
        await db.create_task(
            task_id="t3",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )
        await db.update_task_status("t3", TaskStatus.PROCESSING)

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)

        # Simulate startup recovery (without starting the run loop)
        recovered = await db.recover_orphaned_tasks()
        for tid in recovered:
            await task_queue.enqueue(tid)

        assert task_queue.size() == 1
