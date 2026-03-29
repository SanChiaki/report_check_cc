import json
import sqlite3
from enum import Enum
import aiosqlite


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db_sync()

    def _init_db_sync(self):
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, file_name TEXT NOT NULL, file_path TEXT NOT NULL,
                extra_files TEXT DEFAULT '[]',
                rules TEXT NOT NULL, report_type TEXT, context_vars TEXT,
                status TEXT NOT NULL DEFAULT 'pending', progress INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, started_at TIMESTAMP,
                completed_at TIMESTAMP, error TEXT
            );
            -- 为已有数据库添加 extra_files 列（如果不存在）
            CREATE TABLE IF NOT EXISTS _migrations (key TEXT PRIMARY KEY);
            INSERT OR IGNORE INTO _migrations VALUES ('add_extra_files');
            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL,
                rule_id TEXT NOT NULL, rule_name TEXT NOT NULL, rule_type TEXT NOT NULL,
                status TEXT NOT NULL, location TEXT, message TEXT, suggestion TEXT,
                example TEXT, confidence REAL, execution_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );
            CREATE TABLE IF NOT EXISTS rule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
                report_type TEXT NOT NULL, description TEXT, rules TEXT NOT NULL,
                version TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_check_results_task_id ON check_results(task_id);
        """)
        # 迁移：为旧数据库添加 extra_files 列
        try:
            conn.execute("ALTER TABLE tasks ADD COLUMN extra_files TEXT DEFAULT '[]'")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # 列已存在，忽略
        conn.close()

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
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                INSERT INTO tasks (task_id, file_name, file_path, extra_files, rules, report_type, context_vars)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    file_name,
                    file_path,
                    json.dumps(extra_file_paths or []),
                    json.dumps(rules),
                    report_type,
                    json.dumps(context_vars) if context_vars is not None else None,
                ),
            )
            await db.commit()
        return task_id

    async def get_task(self, task_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                task = dict(row)
                task["rules"] = json.loads(task["rules"])
                if task["context_vars"] is not None:
                    task["context_vars"] = json.loads(task["context_vars"])
                task["extra_files"] = json.loads(task.get("extra_files") or "[]")
                return task

    async def update_task_status(self, task_id: str, status: TaskStatus, error: str | None = None):
        async with aiosqlite.connect(self.db_path) as db:
            if status == TaskStatus.PROCESSING:
                await db.execute(
                    "UPDATE tasks SET status = ?, started_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                    (status.value, task_id),
                )
            elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                await db.execute(
                    "UPDATE tasks SET status = ?, completed_at = CURRENT_TIMESTAMP, error = ? WHERE task_id = ?",
                    (status.value, error, task_id),
                )
            else:
                await db.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status.value, task_id),
                )
            await db.commit()

    async def update_task_progress(self, task_id: str, progress: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET progress = ? WHERE task_id = ?",
                (progress, task_id),
            )
            await db.commit()

    async def save_check_results(self, task_id: str, results: list[dict]):
        async with aiosqlite.connect(self.db_path) as db:
            for result in results:
                await db.execute(
                    """
                    INSERT INTO check_results
                        (task_id, rule_id, rule_name, rule_type, status, location,
                         message, suggestion, example, confidence, execution_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        task_id,
                        result["rule_id"],
                        result["rule_name"],
                        result["rule_type"],
                        result["status"],
                        json.dumps(result.get("location")) if result.get("location") is not None else None,
                        result.get("message"),
                        result.get("suggestion"),
                        result.get("example"),
                        result.get("confidence"),
                        result.get("execution_time"),
                    ),
                )
            await db.commit()

    async def get_check_results(self, task_id: str) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM check_results WHERE task_id = ? ORDER BY id",
                (task_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    result = dict(row)
                    if result["location"] is not None:
                        result["location"] = json.loads(result["location"])
                    results.append(result)
                return results

    async def delete_check_results(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM check_results WHERE task_id = ?", (task_id,)
            )
            await db.commit()

    async def recover_orphaned_tasks(self) -> list[str]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT task_id FROM tasks WHERE status = ?",
                (TaskStatus.PROCESSING.value,),
            ) as cursor:
                rows = await cursor.fetchall()
                task_ids = [row["task_id"] for row in rows]

            for task_id in task_ids:
                await db.execute(
                    "DELETE FROM check_results WHERE task_id = ?", (task_id,)
                )
                await db.execute(
                    "UPDATE tasks SET status = ?, progress = 0 WHERE task_id = ?",
                    (TaskStatus.PENDING.value, task_id),
                )
            await db.commit()
        return task_ids

    async def get_rule_templates(self, report_type: str | None = None) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if report_type is not None:
                async with db.execute(
                    "SELECT * FROM rule_templates WHERE report_type = ? ORDER BY id",
                    (report_type,),
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with db.execute(
                    "SELECT * FROM rule_templates ORDER BY id"
                ) as cursor:
                    rows = await cursor.fetchall()
            templates = []
            for row in rows:
                template = dict(row)
                template["rules"] = json.loads(template["rules"])
                templates.append(template)
            return templates

    async def get_rule_template(self, template_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM rule_templates WHERE id = ?", (template_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                template = dict(row)
                template["rules"] = json.loads(template["rules"])
                return template
