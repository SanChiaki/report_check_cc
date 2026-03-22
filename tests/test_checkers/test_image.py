import pytest
import json
from unittest.mock import AsyncMock

from report_check.checkers.image import ImageChecker
from report_check.parser.excel import ExcelParser
from report_check.storage.cache import ResultCache


class TestImageChecker:
    @pytest.mark.asyncio
    async def test_image_matched(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        check_resp = json.dumps({
            "matched": True,
            "confidence": 0.85,
            "reason": "图片符合要求",
        })
        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=check_resp)
        checker = ImageChecker(report, mm)

        result = await checker.check({
            "requirement": "clean room",
            "min_match_count": 1,
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_no_images(self, sample_excel_no_images):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))

        checker = ImageChecker(report, model_manager=None)

        result = await checker.check({
            "requirement": "clean room",
            "min_match_count": 1,
        })
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_image_filter_by_nearby_text(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        check_resp = json.dumps({
            "matched": True,
            "confidence": 0.9,
            "reason": "matches",
        })
        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=check_resp)
        checker = ImageChecker(report, mm)

        result = await checker.check({
            "requirement": "test image",
            "image_filter": {
                "use_nearby_text": True,
                "keywords": ["移交"],  # Should match nearby cells
            },
            "min_match_count": 1,
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_cache_hit(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=json.dumps({
            "matched": True, "confidence": 0.9, "reason": "ok",
        }))
        checker = ImageChecker(report, mm)
        cache = ResultCache()
        checker.cache = cache

        # First call
        await checker.check({"requirement": "test", "min_match_count": 1})
        first_call_count = mm.call_multimodal_model.call_count

        # Second call should use cache
        await checker.check({"requirement": "test", "min_match_count": 1})
        assert mm.call_multimodal_model.call_count == first_call_count
