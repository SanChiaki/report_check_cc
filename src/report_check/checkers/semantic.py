import json
import logging
import time
from typing import TYPE_CHECKING

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.parser.summarizer import ReportSummarizer

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class SemanticChecker(BaseChecker):
    """Use AI to check semantic content in the report."""

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None):
        super().__init__(report_data, model_manager, artifacts=artifacts)

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        requirement = rule_config.get("requirement", "")
        context_hint = rule_config.get("context_hint", "")

        # Step 1: Locate content
        locations = await self.locate_content(requirement, context_hint)

        if locations is None:
            return CheckResult(
                status="error",
                message="AI 定位内容失败（响应格式异常）",
                execution_time=time.time() - start,
            )

        if not locations:
            return CheckResult(
                status="failed",
                location={"type": "not_found"},
                message=f"未找到符合要求的内容: {requirement}",
                suggestion=f"请在报告中添加相关内容",
                execution_time=time.time() - start,
            )

        # Step 2: Verify content at located region
        summarizer = ReportSummarizer()
        for loc in locations:
            cell_range = loc.get("cell_range", "") or loc.get("cell", "")
            # Parse cell range to get rows
            region_text = self._get_region_text(summarizer, cell_range)

            check_result = await self._semantic_check(region_text, requirement)

            if check_result.get("passed", False):
                return CheckResult(
                    status="passed",
                    location={
                        "type": "cell_range",
                        "value": cell_range,
                        "context": loc.get("context", ""),
                    },
                    message=check_result.get("message", "检查通过"),
                    confidence=check_result.get("confidence", 0.9),
                    execution_time=time.time() - start,
                )

        # All locations checked, none passed
        return CheckResult(
            status="failed",
            location={
                "type": "cell_range",
                "value": locations[0].get("cell_range", ""),
                "context": locations[0].get("context", ""),
            },
            message=check_result.get("message", "内容不满足要求"),
            suggestion=check_result.get("suggestion", f"请确保报告中包含: {requirement}"),
            execution_time=time.time() - start,
        )

    def _get_region_text(self, summarizer: ReportSummarizer, cell_range: str) -> str:
        """Extract text from a cell range string like 'A10:B13' or PDF page like 'page_1'."""
        if not cell_range:
            return summarizer.summarize(self.report_data)

        # Handle PDF page format (e.g., "page_1")
        if cell_range.startswith("page_"):
            try:
                page_num = int(cell_range.split("_")[1])
                # Get text blocks for this page
                page_blocks = [b for b in self.report_data.content_blocks
                              if b.metadata.get("page") == page_num]
                return "\n".join(str(b.content) for b in page_blocks if b.content)
            except (ValueError, IndexError):
                return summarizer.summarize(self.report_data)

        # Handle Excel cell range format
        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            if min_row and max_row:
                return summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            pass

        # Fallback to full summary
        return summarizer.summarize(self.report_data)

    async def _semantic_check(self, content: str, requirement: str) -> dict:
        """Use AI to verify content meets requirement."""
        prompt = f"""请检查以下内容是否满足要求。

要求：{requirement}

内容：
{content}

请以 JSON 格式返回：
{{
  "passed": true/false,
  "message": "检查结论",
  "suggestion": "如果不满足，给出修改建议",
  "confidence": 0.0-1.0
}}"""

        response = await self.call_text_model_with_artifact(
            prompt,
            purpose="semantic_check",
        )
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse semantic check response")
            return {"passed": False, "message": "AI 响应格式异常"}
