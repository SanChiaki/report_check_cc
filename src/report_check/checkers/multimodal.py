import json
import logging
import time
from typing import TYPE_CHECKING

from report_check.checkers.base import BaseChecker, CheckResult

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class MultimodalChecker(BaseChecker):
    """Use multimodal AI to analyze entire report structure (text + images)."""

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None, **kwargs):
        super().__init__(report_data, model_manager, artifacts=artifacts, **kwargs)

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        requirement = rule_config.get("requirement", "")
        context_hint = rule_config.get("context_hint", "")

        if self.artifacts:
            self.artifacts.save_check_detail({
                "requirement": requirement,
                "context_hint": context_hint,
            })

        # Render report as images
        report_images = await self._render_report()

        if not report_images:
            return CheckResult(
                status="error",
                message="无法渲染报告为图片",
                execution_time=time.time() - start,
            )

        # Analyze with multimodal model
        result = await self._analyze_report(report_images, requirement, context_hint)

        return CheckResult(
            status=result.get("status", "error"),
            location=result.get("location", {}),
            message=result.get("message", ""),
            suggestion=result.get("suggestion", ""),
            confidence=result.get("confidence", 0.9),
            execution_time=time.time() - start,
        )

    async def _render_report(self) -> list:
        """Render report pages as images."""
        from report_check.parser.renderer import ReportRenderer

        renderer = ReportRenderer()
        return await renderer.render(self.report_data, self.artifacts)

    async def _analyze_report(self, images: list, requirement: str, context_hint: str) -> dict:
        """Analyze report images with multimodal model."""
        prompt = f"""请分析这份报告，判断是否满足以下要求：

要求：{requirement}
{f'提示：{context_hint}' if context_hint else ''}

请以 JSON 格式返回：
{{
  "status": "passed|failed|error",
  "message": "检查结论",
  "suggestion": "如果不满足，给出修改建议",
  "details": {{}},
  "confidence": 0.0-1.0
}}"""

        # For multi-page reports, analyze each page
        results = []
        for i, img_data in enumerate(images):
            try:
                response = await self.call_multimodal_model_with_artifact(
                    prompt, img_data,
                    purpose=f"analyze_page_{i+1}",
                    image_format="png",
                )
                results.append(self._parse_response(response))
            except Exception as e:
                logger.warning(f"Failed to analyze page {i+1}: {e}")

        # Merge results
        return self._merge_results(results)

    def _parse_response(self, response: str) -> dict:
        """Parse AI response."""
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse multimodal response")
            return {"status": "error", "message": "AI 响应格式异常"}

    def _merge_results(self, results: list) -> dict:
        """Merge results from multiple pages."""
        if not results:
            return {"status": "error", "message": "无分析结果"}

        # If any page passed, consider it passed
        passed = [r for r in results if r.get("status") == "passed"]
        if passed:
            return passed[0]

        # Otherwise return first result
        return results[0]
