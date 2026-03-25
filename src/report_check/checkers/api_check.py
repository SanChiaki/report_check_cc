import base64
import json
import logging
import time
from typing import Any, TYPE_CHECKING

import httpx

from report_check.checkers.base import BaseChecker, CheckResult

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class ApiChecker(BaseChecker):
    """Extract content from report, call external API, validate response."""

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None):
        super().__init__(report_data, model_manager, artifacts=artifacts)

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        extract_config = rule_config.get("extract", {})
        api_config = rule_config.get("api", {})
        validation_config = rule_config.get("validation", {})

        # Save check config to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "extract_config": extract_config,
                "api_config": {k: v for k, v in api_config.items() if k != "headers"},  # Don't log sensitive headers
                "validation_config": validation_config,
            })

        # Step 1: Extract content
        extracted = await self._extract_content(extract_config)
        if extracted is None:
            return CheckResult(
                status="error",
                location={"type": "not_found"},
                message="未找到要提取的内容",
                execution_time=time.time() - start,
            )

        # Save extracted content to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "extracted_content_type": extract_config.get("type", "text"),
                "extracted_location": extracted.get("location", {}),
                "extracted_content_preview": str(extracted.get("content", ""))[:500],
            })

        # Step 2: Call API
        try:
            api_response = await self._call_api(api_config, extracted["content"])
        except Exception as e:
            # Save error to artifacts
            if self.artifacts:
                self.artifacts.save_check_detail({
                    "api_error": str(e),
                })
            return CheckResult(
                status="error",
                location=extracted.get("location", {}),
                message=f"API 调用失败: {str(e)}",
                execution_time=time.time() - start,
            )

        # Save API response to artifacts
        if self.artifacts:
            self.artifacts.save_check_detail({
                "api_response": api_response,
            })

        # Step 3: Validate
        is_valid = self._validate_response(api_response, validation_config)

        return CheckResult(
            status="passed" if is_valid else "failed",
            location=extracted.get("location", {}),
            message="验证通过" if is_valid else validation_config.get("error_message", "验证失败"),
            execution_time=time.time() - start,
        )

    async def _extract_content(self, extract_config: dict) -> dict | None:
        """Extract content from report using AI location or fallback."""
        extract_type = extract_config.get("type", "text")
        description = extract_config.get("description", "")
        context_hint = extract_config.get("context_hint", "")
        fallback = extract_config.get("fallback", "none")

        if extract_type == "image":
            return await self._extract_image(description, context_hint, fallback)
        else:
            return await self._extract_text(description, context_hint)

    async def _extract_image(
        self, description: str, context_hint: str, fallback: str
    ) -> dict | None:
        """Extract an image from the report using AI location or fallback strategy."""
        images = self.report_data.images
        if not images:
            return None

        # Try AI location first
        locations = await self.locate_content(description, context_hint)

        if locations:
            # AI found a location — still pick from available images using the first location hint
            loc = locations[0]
            cell_range = loc.get("cell_range", loc.get("cell", ""))
            # Use fallback order when AI found something (pick last or first per fallback)
            if fallback == "last_image":
                img = images[-1]
            elif fallback == "first_image":
                img = images[0]
            else:
                img = images[0]

            return {
                "content": base64.b64encode(img.data).decode("utf-8"),
                "location": {
                    "type": "image",
                    "value": cell_range or img.anchor.get("cell_ref", ""),
                    "context": loc.get("context", ""),
                },
            }

        # AI did not find content — apply fallback strategy
        if fallback == "last_image":
            img = images[-1]
        elif fallback == "first_image":
            img = images[0]
        else:
            return None

        return {
            "content": base64.b64encode(img.data).decode("utf-8"),
            "location": {
                "type": "image",
                "value": img.anchor.get("cell_ref", ""),
            },
        }

    async def _extract_text(self, description: str, context_hint: str) -> dict | None:
        """Extract text from report using AI location."""
        locations = await self.locate_content(description, context_hint)

        if locations is None or not locations:
            return None

        from report_check.parser.summarizer import ReportSummarizer
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

    async def _call_api(self, api_config: dict, content: Any) -> dict:
        """Call external API."""
        endpoint = api_config.get("endpoint", "")
        method = api_config.get("method", "GET").upper()
        headers = api_config.get("headers", {})
        timeout = api_config.get("timeout", 10)
        body = api_config.get("body", {})
        params = api_config.get("params", {})

        # Replace ${extracted_content} placeholder in body
        body_str = json.dumps(body)
        body_str = body_str.replace("${extracted_content}", str(content))
        body = json.loads(body_str)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "POST":
                resp = await client.post(endpoint, json=body, headers=headers)
            elif method == "GET":
                resp = await client.get(endpoint, params=params, headers=headers)
            else:
                resp = await client.request(method, endpoint, json=body, headers=headers)

            resp.raise_for_status()
            return resp.json()

    def _validate_response(self, response: dict, validation: dict) -> bool:
        """Validate API response using operator."""
        field = validation.get("success_field", "")
        expected = validation.get("success_value", "")
        operator = validation.get("operator", "eq")

        actual = str(response.get(field, ""))

        if operator == "eq":
            return actual == str(expected)
        elif operator == "neq":
            return actual != str(expected)
        elif operator == "contains":
            return str(expected) in actual
        elif operator == "gt":
            try:
                return float(actual) > float(expected)
            except ValueError:
                return False
        elif operator == "gte":
            try:
                return float(actual) >= float(expected)
            except ValueError:
                return False

        return False
