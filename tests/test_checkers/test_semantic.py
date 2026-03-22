import pytest
import json
from unittest.mock import AsyncMock

from report_check.checkers.semantic import SemanticChecker
from report_check.parser.excel import ExcelParser


def make_mock_model_manager(locate_response: str, check_response: str):
    mm = AsyncMock()
    mm.call_text_model = AsyncMock(side_effect=[locate_response, check_response])
    return mm


class TestSemanticChecker:
    @pytest.mark.asyncio
    async def test_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A10:B13", "context": "移交记录", "confidence": 0.9}],
            "reason": "found handover section",
        })
        check_resp = json.dumps({
            "passed": True,
            "message": "包含移交人、移交时间、移交命令",
            "confidence": 0.95,
        })
        mm = make_mock_model_manager(locate_resp, check_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "移交记录中要包含移交人、移交时间、移交命令",
            "context_hint": "移交相关章节",
            "model": "text",
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_failed_content_not_found(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": False,
            "locations": [],
            "reason": "not found",
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "需要包含不存在的内容",
        })
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_failed_check(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A10:B13", "context": "移交", "confidence": 0.9}],
            "reason": "found",
        })
        check_resp = json.dumps({
            "passed": False,
            "message": "缺少移交命令",
            "suggestion": "请添加移交命令字段",
            "confidence": 0.8,
        })
        mm = make_mock_model_manager(locate_resp, check_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "需要包含移交命令",
        })
        assert result.status == "failed"
