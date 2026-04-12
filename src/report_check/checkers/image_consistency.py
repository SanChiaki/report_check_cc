import json
import logging
import time
from typing import TYPE_CHECKING

from report_check.checkers.base import BaseChecker, CheckResult

if TYPE_CHECKING:
    from report_check.storage.artifacts import CheckArtifact

logger = logging.getLogger(__name__)


class ImageConsistencyChecker(BaseChecker):
    """Check if images match their corresponding check item descriptions.

    This checker analyzes reports to identify check items and their associated images,
    then verifies if each image content matches the description of its check item.

    Example rule config:
    {
        "type": "image_consistency",
        "name": "检查项配图一致性检查",
        "config": {
            "requirement": "检查项的配图是否符合检查项的描述",
            "strict_mode": false  # Optional: if true, requires high confidence match
        }
    }
    """

    def __init__(self, report_data, model_manager, artifacts: "CheckArtifact | None" = None, **kwargs):
        super().__init__(report_data, model_manager, artifacts=artifacts, **kwargs)

    async def check(self, rule_config: dict) -> CheckResult:
        """Execute image consistency check.

        Args:
            rule_config: Configuration dict containing:
                - requirement: Description of what to check (default: "检查项的配图是否符合检查项的描述")
                - strict_mode: If True, requires high confidence (>0.8) for matches

        Returns:
            CheckResult with status, message, and detailed findings
        """
        start = time.time()

        config = rule_config.get("config", {})
        requirement = config.get("requirement", "检查项的配图是否符合检查项的描述")
        strict_mode = config.get("strict_mode", False)

        if self.artifacts:
            self.artifacts.save_check_detail({
                "requirement": requirement,
                "strict_mode": strict_mode,
            })

        # Render report as images
        report_images = await self._render_report()

        if not report_images:
            return CheckResult(
                status="error",
                message="无法渲染报告为图片",
                execution_time=time.time() - start,
            )

        # Analyze each page for check items and their images
        all_items = []
        for page_idx, img_data in enumerate(report_images):
            try:
                page_items = await self._analyze_page(
                    img_data, page_idx + 1, requirement
                )
                all_items.extend(page_items)
            except Exception as e:
                logger.warning(f"Failed to analyze page {page_idx + 1}: {e}")

        if not all_items:
            return CheckResult(
                status="passed",
                message="报告中未发现检查项",
                execution_time=time.time() - start,
            )

        # Calculate results
        matched_count = sum(1 for item in all_items if item.get("matched", False))
        total_count = len(all_items)

        # Determine overall status
        if strict_mode:
            # In strict mode, all items must match with high confidence
            all_passed = all(
                item.get("matched", False) and item.get("confidence", 0) > 0.8
                for item in all_items
            )
            status = "passed" if all_passed else "failed"
        else:
            # In normal mode, majority match is considered passed
            status = "passed" if matched_count >= total_count / 2 else "failed"

        # Build detailed message
        failed_items = [item for item in all_items if not item.get("matched", False)]

        message_parts = [
            f"发现 {total_count} 个检查项，{matched_count} 项配图符合描述，{len(failed_items)} 项不符。"
        ]

        if failed_items:
            message_parts.append("\n不符合项：")
            for item in failed_items[:5]:  # Limit to first 5
                message_parts.append(
                    f"\n- {item.get('item_name', '未知检查项')}: "
                    f"{item.get('image_content', 'N/A')[:50]}..."
                )

        return CheckResult(
            status=status,
            message="\n".join(message_parts),
            suggestion=self._build_suggestion(failed_items),
            confidence=matched_count / total_count if total_count > 0 else 0,
            execution_time=time.time() - start,
            details={
                "total_items": total_count,
                "matched_items": matched_count,
                "failed_items": len(failed_items),
                "check_items": all_items,
            },
        )

    async def _render_report(self) -> list:
        """Render report pages as images."""
        return await self.render_report(self.report_data)

    async def _analyze_page(
        self, img_data: bytes, page_num: int, requirement: str
    ) -> list:
        """Analyze a single page for check items and their images.

        Args:
            img_data: Page image data
            page_num: Page number (1-indexed)
            requirement: The checking requirement description

        Returns:
            List of check item results
        """
        prompt = self._build_prompt(requirement)

        response = await self.call_multimodal_model_with_artifact(
            prompt, img_data,
            purpose=f"image_consistency_page_{page_num}",
            image_format="png",
        )

        return self._parse_response(response)

    def _build_prompt(self, requirement: str) -> str:
        """Build the analysis prompt."""
        return f"""你是一个质检报告审核专家。请仔细观察这份报告页面，完成以下任务：

1. **自主识别检查项**：分析报告内容，找出所有带有配图的检查项（检查项通常是某种验证、检测或审查的条目，可能有不同命名方式如"XX检查"、"XX检测"、"XX检验"等，也可能直接描述检查内容）
2. **定位配图**：找到每个检查项对应的配图（通常在检查项旁边或下方）
3. **一致性判断**：判断每张配图是否与其对应的检查项描述相符

要求：{requirement}

请以 JSON 格式返回检查结果：
{{
  "check_items": [
    {{
      "item_name": "检查项名称（如：机柜检查）",
      "location": "检查项在报告中的位置描述",
      "img_id": "配图标识（如果有的话）",
      "matched": true/false,
      "confidence": 0.0-1.0,
      "reason": "判断理由（详细说明图片内容，以及为什么符合或不符合检查项描述）",
      "image_content": "图片中实际展示的内容"
    }}
  ],
  "summary": "整体检查总结（如：发现X个检查项，其中Y项配图符合要求，Z项不符）"
}}

重要：
- 必须自主分析报告，识别出所有包含配图的检查项，不要遗漏
- 检查项命名方式可能多样（检查/检测/检验等），请根据上下文灵活判断
- 对于每个识别出的检查项，必须找到其对应的配图进行判断
- reason 要具体，说明你在图片中看到了什么，以及为什么符合或不符合该项检查的预期
- 如果某个检查项没有配图，明确指出"未找到配图"
- 如果配图与检查项明显不符（如检查"机柜"但配图是"办公桌"），标记为 false"""

    def _parse_response(self, response: str) -> list:
        """Parse AI response and extract check items.

        Args:
            response: AI model response text

        Returns:
            List of check item dictionaries
        """
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)
            return data.get("check_items", [])
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning(f"Failed to parse response: {e}")
            return []

    def _build_suggestion(self, failed_items: list) -> str:
        """Build suggestion message for failed items.

        Args:
            failed_items: List of failed check items

        Returns:
            Suggestion string
        """
        if not failed_items:
            return ""

        suggestions = ["请检查以下配图是否正确："]
        for item in failed_items[:3]:
            suggestions.append(
                f"\n- {item.get('item_name', '未知')}: "
                f"当前配图显示'{item.get('image_content', 'N/A')[:40]}...'，"
                f"建议更换为符合'{item.get('item_name')}'主题的图片"
            )

        return "\n".join(suggestions)
