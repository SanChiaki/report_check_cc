import pytest
from pathlib import Path
from report_check.storage.database import Database, TaskStatus


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


class TestDatabase:
    @pytest.mark.asyncio
    async def test_create_and_get_task(self, db):
        task_id = await db.create_task(task_id="test-001", file_name="report.xlsx", file_path="/tmp/report.xlsx", rules={"rules": []}, report_type="server")
        assert task_id == "test-001"
        task = await db.get_task("test-001")
        assert task is not None
        assert task["file_name"] == "report.xlsx"
        assert task["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, db):
        task = await db.get_task("nonexistent")
        assert task is None

    @pytest.mark.asyncio
    async def test_update_task_status(self, db):
        await db.create_task(task_id="test-002", file_name="r.xlsx", file_path="/tmp/r.xlsx", rules={"rules": []})
        await db.update_task_status("test-002", TaskStatus.PROCESSING)
        task = await db.get_task("test-002")
        assert task["status"] == "processing"

    @pytest.mark.asyncio
    async def test_update_task_progress(self, db):
        await db.create_task(task_id="test-003", file_name="r.xlsx", file_path="/tmp/r.xlsx", rules={"rules": []})
        await db.update_task_progress("test-003", 50)
        task = await db.get_task("test-003")
        assert task["progress"] == 50

    @pytest.mark.asyncio
    async def test_save_and_get_check_results(self, db):
        await db.create_task(task_id="test-004", file_name="r.xlsx", file_path="/tmp/r.xlsx", rules={"rules": []})
        await db.save_check_results("test-004", [{"rule_id": "rule_001", "rule_name": "检查交付内容", "rule_type": "text", "status": "passed", "location": {"type": "cell_range", "value": "A5"}, "message": "找到关键词", "suggestion": "", "example": "", "confidence": 1.0, "execution_time": 0.1}])
        results = await db.get_check_results("test-004")
        assert len(results) == 1
        assert results[0]["rule_id"] == "rule_001"

    @pytest.mark.asyncio
    async def test_delete_check_results(self, db):
        await db.create_task(task_id="test-005", file_name="r.xlsx", file_path="/tmp/r.xlsx", rules={"rules": []})
        await db.save_check_results("test-005", [{"rule_id": "r1", "rule_name": "test", "rule_type": "text", "status": "passed", "location": {}, "message": "", "suggestion": "", "example": "", "confidence": 1.0, "execution_time": 0.1}])
        await db.delete_check_results("test-005")
        results = await db.get_check_results("test-005")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_recover_orphaned_tasks(self, db):
        await db.create_task(task_id="orphan-001", file_name="r.xlsx", file_path="/tmp/r.xlsx", rules={"rules": []})
        await db.update_task_status("orphan-001", TaskStatus.PROCESSING)
        task_ids = await db.recover_orphaned_tasks()
        assert "orphan-001" in task_ids
        task = await db.get_task("orphan-001")
        assert task["status"] == "pending"
