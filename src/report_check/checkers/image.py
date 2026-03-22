import json
import logging
import time

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.storage.cache import ResultCache

logger = logging.getLogger(__name__)


class ImageChecker(BaseChecker):
    """Check images in the report using multimodal AI."""

    def __init__(self, report_data, model_manager):
        super().__init__(report_data, model_manager)
        self.cache = ResultCache()

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        requirement = rule_config.get("requirement", "")
        min_match = rule_config.get("min_match_count", 1)
        image_filter = rule_config.get("image_filter", {})

        images = self._get_images(image_filter)

        if not images:
            return CheckResult(
                status="failed",
                location={"type": "images", "count": 0},
                message="报告中未找到图片",
                suggestion="请在报告中添加相关图片",
                execution_time=time.time() - start,
            )

        matched = []
        for img in images:
            cache_key = self.cache.get_cache_key(img.data, requirement)
            cached = self.cache.get(cache_key)

            if cached is not None:
                result = cached
            else:
                result = await self._check_image(img, requirement)
                self.cache.set(cache_key, result)

            if result.get("matched", False):
                matched.append((img, result))

        if len(matched) >= min_match:
            img, res = matched[0]
            return CheckResult(
                status="passed",
                location={
                    "type": "image",
                    "value": img.anchor.get("cell_ref", ""),
                    "context": f"找到 {len(matched)} 张符合要求的图片",
                },
                message=f"找到 {len(matched)} 张符合要求的图片",
                confidence=res.get("confidence", 0.9),
                execution_time=time.time() - start,
            )
        else:
            return CheckResult(
                status="failed",
                location={"type": "images", "count": len(images)},
                message=f"未找到足够的符合要求的图片 (需要 {min_match}，找到 {len(matched)})",
                suggestion="请添加符合要求的图片",
                execution_time=time.time() - start,
            )

    def _get_images(self, image_filter: dict) -> list:
        """Filter images based on nearby text keywords."""
        all_images = self.report_data.images
        if not image_filter.get("use_nearby_text", False):
            return all_images

        keywords = image_filter.get("keywords", [])
        if not keywords:
            return all_images

        filtered = []
        for img in all_images:
            nearby_text = " ".join(str(c.value) for c in img.nearby_cells)
            if any(kw in nearby_text for kw in keywords):
                filtered.append(img)

        # Fallback to all if no filter matches
        return filtered if filtered else all_images

    async def _check_image(self, img, requirement: str) -> dict:
        """Use multimodal model to check a single image."""
        if self.model_manager is None:
            return {"matched": False, "confidence": 0, "reason": "no model"}

        prompt = f"""请判断这张图片是否符合以下要求：{requirement}

请以 JSON 格式返回：
{{
  "matched": true/false,
  "confidence": 0.0-1.0,
  "reason": "判断理由"
}}"""

        try:
            response = await self.model_manager.call_multimodal_model(
                prompt, img.data
            )
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Image check failed: {e}")
            return {"matched": False, "confidence": 0, "reason": str(e)}
