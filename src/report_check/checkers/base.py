from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import json
import asyncio
import logging

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single check rule."""
    status: str = "error"
    location: dict = field(default_factory=dict)
    message: str = ""
    suggestion: str = ""
    example: str = ""
    confidence: float = 1.0
    execution_time: float = 0.0
    rule_id: str = ""
    rule_name: str = ""
    rule_type: str = ""


class BaseChecker(ABC):
    """Abstract base class for all checkers."""

    def __init__(self, report_data, model_manager):
        """Initialize checker with report data and model manager.

        Args:
            report_data: ReportData instance
            model_manager: ModelManager instance
        """
        self.report_data = report_data
        self.model_manager = model_manager

    @abstractmethod
    def check(self, rule_config) -> CheckResult:
        """Execute a check rule.

        Args:
            rule_config: Configuration dict for the rule

        Returns:
            CheckResult instance
        """
        pass

    async def locate_content(self, description: str, context_hint: Optional[str] = None) -> Optional[list]:
        """Use AI to locate content matching description.

        Args:
            description: Description of content to find
            context_hint: Optional hint about where to look

        Returns:
            List of locations or None if not found
        """
        from report_check.parser.summarizer import ReportSummarizer
        summarizer = ReportSummarizer()
        report_summary = summarizer.summarize(self.report_data)

        prompt = f"""以下是 Excel 报告的内容摘要：

{report_summary}

请在上述报告中找出符合以下描述的内容：
描述：{description}
{f'提示：{context_hint}' if context_hint else ''}

请以 JSON 格式回复，格式如下：
{{
  "found": true/false,
  "locations": [
    {{
      "sheet": "工作表名",
      "cell": "A1",
      "cell_range": "A1:B3",
      "row": 1,
      "column": 1,
      "content": "找到的文本内容",
      "context": "上下文说明"
    }}
  ]
}}

只返回 JSON，不要有其他文字。"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.model_manager.call_text_model(prompt)
                return self._parse_location_response(response)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to locate content after {max_retries} attempts: {e}")
                    return None
                await asyncio.sleep(0.5)

    def _parse_location_response(self, response: str) -> Optional[list]:
        """Parse location response from AI model.

        Args:
            response: Response text from model

        Returns:
            List of locations, empty list if found=false, None on parse error
        """
        try:
            # Extract JSON from markdown code blocks if present
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()

            data = json.loads(response)

            if not data.get("found", False):
                return []

            return data.get("locations", [])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse location response: {e}")
            return None
