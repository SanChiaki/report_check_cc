import json
import logging
import time
from typing import Any, TYPE_CHECKING

import httpx

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.parser.summarizer import ReportSummarizer

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class ExternalDataChecker(BaseChecker):
    """Extract data from report, fetch external data, use AI to compare."""

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None):
        super().__init__(report_data, model_manager, artifacts=artifacts)
    """Extract data from report, fetch external data, use AI to compare."""

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        extract_config = rule_config.get("extract", {})
        api_config = rule_config.get("external_api", {})
        analysis_config = rule_config.get("analysis", {})

        # Save check config to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "extract_config": extract_config,
                "external_api_config": {k: v for k, v in api_config.items() if k != "headers"},
                "analysis_config": analysis_config,
            })

        # Step 1: Extract report data
        extracted = await self._extract_data(extract_config)
        if extracted is None:
            return CheckResult(
                status="failed",
                location={"type": "not_found"},
                message="未找到要提取的内容",
                execution_time=time.time() - start,
            )

        # Save extracted content to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "extracted_location": extracted.get("location", {}),
                "extracted_content_preview": str(extracted.get("content", ""))[:500],
            })

        # Step 2: Fetch external data
        try:
            external_data = await self._fetch_external_data(api_config)
        except Exception as e:
            # Save error to artifacts
            if self.artifacts:
                self.artifacts.save_check_detail({
                    "external_api_error": str(e),
                })
            return CheckResult(
                status="error",
                location=extracted.get("location", {}),
                message=f"获取外部数据失败: {str(e)}",
                execution_time=time.time() - start,
            )

        # Save external data to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "external_data_preview": str(external_data)[:500],
            })

        # Step 3: AI analysis
        analysis_result = await self._analyze(
            extracted["content"], external_data, analysis_config
        )

        # Save analysis result to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "ai_analysis_result": analysis_result,
            })

        return CheckResult(
            status="passed" if analysis_result.get("passed") else "failed",
            location=extracted.get("location", {}),
            message=analysis_result.get("message", ""),
            suggestion=analysis_result.get("suggestion", ""),
            confidence=analysis_result.get("confidence", 0.9),
            execution_time=time.time() - start,
        )

    async def _extract_data(self, extract_config: dict) -> dict | None:
        """Use AI to locate and extract data from report."""
        description = extract_config.get("description", "")
        context_hint = extract_config.get("context_hint", "")

        locations = await self.locate_content(description, context_hint)
        if locations is None or not locations:
            return None

        summarizer = ReportSummarizer()
        loc = locations[0]
        cell_range = loc.get("cell_range", loc.get("cell", ""))

        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            text = summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            text = summarizer.summarize(self.report_data)

        return {
            "content": text,
            "location": {"type": "cell_range", "value": cell_range, "context": loc.get("context", "")},
        }

    async def _fetch_external_data(self, api_config: dict) -> Any:
        """Fetch data from external API."""
        endpoint = api_config.get("endpoint", "")
        method = api_config.get("method", "GET").upper()
        headers = api_config.get("headers", {})
        params = api_config.get("params", {})
        response_path = api_config.get("response_path", "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(endpoint, params=params, headers=headers)
            else:
                resp = await client.request(method, endpoint, headers=headers)

            await resp.raise_for_status()
            data = await resp.json()

        # Navigate response path (e.g., "data.devices")
        if response_path:
            for key in response_path.split("."):
                data = data[key]

        return data

    async def _analyze(
        self, report_data: str, external_data: Any, analysis_config: dict
    ) -> dict:
        """Use AI to compare report data with external data."""
        requirement = analysis_config.get("requirement", "")

        prompt = f"""请根据外部数据检查报告数据是否满足要求。

要求：{requirement}

报告数据：
{report_data}

外部数据：
{json.dumps(external_data, ensure_ascii=False, indent=2) if not isinstance(external_data, str) else external_data}

请以 JSON 格式返回：
{{
  "passed": true/false,
  "message": "分析结论",
  "suggestion": "如果不满足，给出修改建议",
  "confidence": 0.0-1.0
}}"""

        response = await self.call_text_model_with_artifact(
            prompt,
            purpose="external_data_analysis",
        )
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {"passed": False, "message": "AI 响应格式异常"}
