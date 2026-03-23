from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional
import json
import asyncio
import logging

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

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

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None):
        """Initialize checker with report data and model manager.

        Args:
            report_data: ReportData instance
            model_manager: ModelManager instance
            artifacts: Optional CheckArtifact instance for recording execution details
        """
        self.report_data = report_data
        self.model_manager = model_manager
        self.artifacts = artifacts

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

        # 根据报告类型调整提示词
        if self.report_data.source_type == "excel":
            report_type = "Excel 报告"
            location_format = """
    {{
      "sheet": "工作表名",
      "cell": "A1",
      "cell_range": "A1:B3",
      "row": 1,
      "column": 1,
      "content": "找到的文本内容",
      "context": "上下文说明"
    }}"""
        else:  # PDF
            report_type = "PDF 报告"
            location_format = """
    {{
      "page": 1,
      "location": "page_1",
      "content": "找到的文本内容",
      "context": "上下文说明"
    }}"""

        prompt = f"""以下是 {report_type} 的内容摘要：

{report_summary}

请在上述报告中找出符合以下描述的内容：
描述：{description}
{f'提示：{context_hint}' if context_hint else ''}

请以 JSON 格式回复，格式如下：
{{
  "found": true/false,
  "locations": [{location_format}
  ]
}}

只返回 JSON，不要有其他文字。"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await self.model_manager.call_text_model(prompt)
                result = self._parse_location_response(response)

                # Save location attempt to artifacts
                if self.artifacts:
                    self.artifacts.save_location_attempt(
                        description=description,
                        prompt=prompt,
                        response=response,
                        result={"locations": result} if result else None,
                        error=None if result else "Parse failed or not found"
                    )

                return result
            except Exception as e:
                # Save failed attempt to artifacts
                if self.artifacts:
                    self.artifacts.save_location_attempt(
                        description=description,
                        prompt=prompt,
                        response="",
                        result=None,
                        error=f"Attempt {attempt + 1}/{max_retries}: {str(e)}"
                    )

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

    async def call_text_model_with_artifact(self, prompt: str, purpose: str, **kwargs) -> str:
        """调用文本模型并记录到 artifacts

        Args:
            prompt: 提示词
            purpose: 调用目的描述，如 "locate_content", "semantic_check"
            **kwargs: 传递给 model_manager 的参数

        Returns:
            模型响应文本
        """
        import time
        start = time.time()
        error = None
        response = None

        try:
            response = await self.model_manager.call_text_model(prompt, **kwargs)
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            if self.artifacts:
                duration = (time.time() - start) * 1000
                self.artifacts.task.save_ai_call(
                    call_type="text",
                    purpose=purpose,
                    request={"prompt": prompt, "model": getattr(self.model_manager, 'text_model', 'unknown')},
                    response=response,
                    duration_ms=duration,
                    error=error,
                )

    async def call_multimodal_model_with_artifact(self, prompt: str, image: bytes, purpose: str, **kwargs) -> str:
        """调用多模态模型并记录到 artifacts

        Args:
            prompt: 提示词
            image: 图片数据
            purpose: 调用目的描述，如 "image_check"
            **kwargs: 传递给 model_manager 的参数

        Returns:
            模型响应文本
        """
        import time
        start = time.time()
        error = None
        response = None

        try:
            response = await self.model_manager.call_multimodal_model(prompt, image, **kwargs)
            return response
        except Exception as e:
            error = str(e)
            raise
        finally:
            if self.artifacts:
                duration = (time.time() - start) * 1000
                self.artifacts.task.save_ai_call(
                    call_type="multimodal",
                    purpose=purpose,
                    request={"prompt": prompt, "model": getattr(self.model_manager, 'multimodal_model', 'unknown')},
                    response=response,
                    duration_ms=duration,
                    error=error,
                )
