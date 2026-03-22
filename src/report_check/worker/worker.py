import asyncio
import dataclasses
import logging
import time

from report_check.checkers.factory import CheckerFactory
from report_check.engine.rule_engine import RuleEngine
from report_check.engine.variable_resolver import VariableResolver
from report_check.models.manager import ModelManager
from report_check.parser.excel import ExcelParser
from report_check.storage.database import Database, TaskStatus
from report_check.worker.queue import TaskQueue

logger = logging.getLogger(__name__)


def _serialize_location(location) -> dict:
    """Convert location to a plain JSON-serializable dict."""
    if location is None:
        return {}
    if isinstance(location, dict):
        return location
    if dataclasses.is_dataclass(location):
        return dataclasses.asdict(location)
    return {}


class BackgroundWorker:
    """Process check tasks from the queue."""

    def __init__(
        self,
        db: Database,
        model_manager: ModelManager,
        task_queue: TaskQueue,
    ):
        self.db = db
        self.model_manager = model_manager
        self.task_queue = task_queue
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True

        # Recover orphaned tasks
        recovered = await self.db.recover_orphaned_tasks()
        for tid in recovered:
            await self.task_queue.enqueue(tid)
            logger.info(f"Re-enqueued recovered task: {tid}")

        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        while self._running:
            try:
                task_id = await self.task_queue.dequeue()
                await self._process_task(task_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)

    async def _process_task(self, task_id: str):
        task = await self.db.get_task(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return

        try:
            await self.db.update_task_status(task_id, TaskStatus.PROCESSING)

            # Step 1: Parse Excel
            await self.db.update_task_progress(task_id, 10)
            parser = ExcelParser()
            report_data = parser.parse(task["file_path"])

            # Step 2: Load rules and resolve variables
            await self.db.update_task_progress(task_id, 20)
            engine = RuleEngine()
            user_rules = task["rules"].get("rules", [])
            rules = engine.get_rules(user_rules=user_rules)

            # Resolve variables in rule configs
            context_vars = task.get("context_vars", {}) or {}
            extra_context = {"task_id": task_id, **context_vars}
            resolver = VariableResolver()
            for rule in rules:
                try:
                    rule["config"] = resolver.resolve_dict(rule["config"], extra_context)
                except Exception as e:
                    logger.warning(f"Variable resolution failed for rule {rule['id']}: {e}")

            # Step 3: Execute checks
            results = []
            api_failure_counts: dict[str, int] = {}

            for i, rule in enumerate(rules):
                progress = 20 + int((i / max(len(rules), 1)) * 70)
                await self.db.update_task_progress(task_id, progress)

                start = time.time()

                # Check circuit breaker for API rules
                rule_type = rule["type"]
                if rule_type in ("api", "external_data"):
                    api_name = rule.get("config", {}).get("api", {}).get("name") or \
                               rule.get("config", {}).get("external_api", {}).get("name", "")
                    if api_failure_counts.get(api_name, 0) >= 3:
                        results.append({
                            "rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "rule_type": rule_type,
                            "status": "error",
                            "location": {},
                            "message": f"API {api_name} 连续失败，已跳过",
                            "suggestion": "",
                            "example": "",
                            "confidence": 0,
                            "execution_time": 0,
                        })
                        continue

                checker = CheckerFactory.create(rule_type, report_data, self.model_manager)
                check_result = checker.check(rule["config"])
                if asyncio.iscoroutine(check_result):
                    result = await check_result
                else:
                    result = check_result
                result.rule_id = rule["id"]
                result.rule_name = rule["name"]
                result.rule_type = rule_type
                result.execution_time = time.time() - start

                # Track API failures
                if result.status == "error" and rule_type in ("api", "external_data"):
                    api_name = rule.get("config", {}).get("api", {}).get("name") or \
                               rule.get("config", {}).get("external_api", {}).get("name", "")
                    api_failure_counts[api_name] = api_failure_counts.get(api_name, 0) + 1

                results.append({
                    "rule_id": result.rule_id,
                    "rule_name": result.rule_name,
                    "rule_type": result.rule_type,
                    "status": result.status,
                    "location": _serialize_location(result.location),
                    "message": result.message,
                    "suggestion": result.suggestion,
                    "example": result.example,
                    "confidence": result.confidence,
                    "execution_time": result.execution_time,
                })

            # Step 4: Save results
            await self.db.update_task_progress(task_id, 95)
            await self.db.save_check_results(task_id, results)
            await self.db.update_task_status(task_id, TaskStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await self.db.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
