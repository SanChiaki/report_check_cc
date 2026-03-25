import asyncio
import dataclasses
import logging
import time
from pathlib import Path

from report_check.checkers.factory import CheckerFactory
from report_check.engine.rule_engine import RuleEngine
from report_check.engine.variable_resolver import VariableResolver
from report_check.models.manager import ModelManager
from report_check.parser.excel import ExcelParser
from report_check.parser.pdf import PDFParser
from report_check.storage.artifacts import ArtifactsManager, TaskArtifacts
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
        artifacts_manager: ArtifactsManager | None = None,
    ):
        self.db = db
        self.model_manager = model_manager
        self.task_queue = task_queue
        self.artifacts_manager = artifacts_manager
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

        # Initialize artifacts for this task
        artifacts: TaskArtifacts | None = None
        if self.artifacts_manager:
            artifacts = self.artifacts_manager.init_task(task_id)
            logger.info(f"Initialized artifacts for task {task_id}")

        try:
            await self.db.update_task_status(task_id, TaskStatus.PROCESSING)

            # Step 1: Parse file (Excel or PDF)
            await self.db.update_task_progress(task_id, 10)
            file_path = task["file_path"]
            file_name = task["file_name"]

            # Copy original file to artifacts
            if artifacts:
                try:
                    original_data = Path(file_path).read_bytes()
                    artifacts.save_upload(file_name, original_data, "original")
                except Exception as e:
                    logger.warning(f"Failed to save original file to artifacts: {e}")

            # Parse with artifact recording
            if file_path.endswith(".pdf"):
                parser = PDFParser(artifacts=artifacts, model_manager=self.model_manager)
            else:
                parser = ExcelParser(artifacts=artifacts)

            report_data = parser.parse(file_path)

            # For scanned PDFs with text rules, extract text using vision model
            if (
                file_path.endswith(".pdf")
                and report_data.metadata.get("is_scanned")
                and any(r.get("type") == "text" for r in user_rules)
            ):
                logger.info(f"Scanned PDF with text rules detected, extracting text with vision model")
                ocr_blocks = await parser.extract_text_with_vision(report_data)
                if ocr_blocks:
                    # Prepend OCR text blocks before image placeholders
                    report_data.content_blocks = ocr_blocks + report_data.content_blocks
                    logger.info(f"Added {len(ocr_blocks)} OCR text blocks to report data")

            # Save parsed data summary
            if artifacts:
                artifacts.save_report_data_summary({
                    "file_name": report_data.file_name,
                    "source_type": report_data.source_type,
                    "content_blocks": [
                        {
                            "content": str(b.content)[:200] if b.content else "",
                            "location": b.location,
                            "content_type": b.content_type,
                            "metadata": b.metadata,
                        }
                        for b in report_data.content_blocks
                    ],
                    "images": [
                        {
                            "id": img.id,
                            "format": img.format,
                            "anchor": img.anchor,
                        }
                        for img in report_data.images
                    ],
                    "metadata": report_data.metadata,
                })

            # Step 2: Load rules and resolve variables
            await self.db.update_task_progress(task_id, 20)
            engine = RuleEngine()
            user_rules = task["rules"].get("rules", [])

            # Save user rules
            if artifacts:
                artifacts.save_user_rules(user_rules)

            rules = engine.get_rules(user_rules=user_rules)

            # Save merged rules
            if artifacts:
                artifacts.save_merged_rules(rules)

            # Resolve variables in rule configs
            context_vars = task.get("context_vars", {}) or {}
            extra_context = {"task_id": task_id, **context_vars}
            resolver = VariableResolver()

            resolved_rules = []
            for rule in rules:
                try:
                    resolved_rule = rule.copy()
                    resolved_rule["config"] = resolver.resolve_dict(rule["config"], extra_context)
                    resolved_rules.append(resolved_rule)
                except Exception as e:
                    logger.warning(f"Variable resolution failed for rule {rule['id']}: {e}")
                    resolved_rules.append(rule)

            # Save resolved rules
            if artifacts:
                artifacts.save_resolved_rules(resolved_rules)

            # Step 3: Execute checks
            results = []
            api_failure_counts: dict[str, int] = {}

            for i, rule in enumerate(resolved_rules):
                progress = 20 + int((i / max(len(resolved_rules), 1)) * 70)
                await self.db.update_task_progress(task_id, progress)

                start = time.time()

                # Check circuit breaker for API rules
                rule_type = rule["type"]
                if rule_type in ("api", "external_data"):
                    api_name = rule.get("config", {}).get("api", {}).get("name") or \
                               rule.get("config", {}).get("external_api", {}).get("name", "")
                    if api_failure_counts.get(api_name, 0) >= 3:
                        result_data = {
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
                        }
                        results.append(result_data)

                        # Save skipped check artifact
                        if artifacts:
                            check_artifact = artifacts.init_check_artifact(rule["id"], rule_type, rule["name"])
                            check_artifact.save_config(rule.get("config", {}))
                            check_artifact.save_result(result_data)
                        continue

                # Initialize check artifact
                check_artifact = None
                if artifacts:
                    check_artifact = artifacts.init_check_artifact(rule["id"], rule_type, rule["name"])
                    check_artifact.save_config(rule.get("config", {}))

                # Create checker with artifact support
                checker = CheckerFactory.create(
                    rule_type, report_data, self.model_manager,
                    artifacts=check_artifact
                )

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

                result_data = {
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
                }
                results.append(result_data)

                # Save check result to artifact
                if check_artifact:
                    check_artifact.save_result(result_data)

            # Step 4: Save results
            await self.db.update_task_progress(task_id, 95)
            await self.db.save_check_results(task_id, results)

            # Save final artifacts
            if artifacts:
                artifacts.save_check_results(results)
                artifacts.save_summary({
                    "task_id": task_id,
                    "file_name": file_name,
                    "status": "completed",
                    "total_rules": len(resolved_rules),
                    "passed": sum(1 for r in results if r["status"] == "passed"),
                    "failed": sum(1 for r in results if r["status"] == "failed"),
                    "error": sum(1 for r in results if r["status"] == "error"),
                })

            await self.db.update_task_status(task_id, TaskStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await self.db.update_task_status(task_id, TaskStatus.FAILED, error=str(e))

            # Save error to artifacts
            if artifacts:
                artifacts.save_summary({
                    "task_id": task_id,
                    "file_name": task.get("file_name", "unknown"),
                    "status": "failed",
                    "error": str(e),
                })
