import pytest
import json
import asyncio
from unittest.mock import AsyncMock, Mock, patch

from report_check.checkers.external import ExternalDataChecker
from report_check.parser.excel import ExcelParser


class TestExternalDataChecker:
    @pytest.mark.asyncio
    async def test_external_data_check_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A6:A7", "context": "设备列表", "confidence": 0.9}],
            "reason": "found",
        })
        analysis_resp = json.dumps({
            "passed": True,
            "message": "所有设备都在清单中",
            "confidence": 0.95,
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(side_effect=[locate_resp, analysis_resp])

        checker = ExternalDataChecker(report, mm)

        with patch("report_check.checkers.external.httpx.AsyncClient") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = {"data": {"devices": ["server1", "server2"]}}
            mock_resp.raise_for_status = Mock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "text",
                    "description": "设备列表",
                    "context_hint": "设备相关章节",
                },
                "external_api": {
                    "name": "inventory",
                    "endpoint": "https://api.example.com/devices",
                    "method": "GET",
                    "response_path": "data.devices",
                },
                "analysis": {
                    "requirement": "报告中的设备必须在清单中",
                },
            })
            assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_external_data_checker_respects_shared_external_api_limiter(self, sample_excel_path):
        from report_check.core.concurrency import ExternalApiLimiter

        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A6:A7", "context": "设备列表", "confidence": 0.9}],
            "reason": "found",
        })
        analysis_resp = json.dumps({
            "passed": True,
            "message": "所有设备都在清单中",
            "confidence": 0.95,
        })

        async def fake_call_text_model(prompt: str, **kwargs):
            if "请在上述报告中找出符合以下描述的内容" in prompt:
                return locate_resp
            return analysis_resp

        mm = AsyncMock()
        mm.call_text_model = AsyncMock(side_effect=fake_call_text_model)

        limiter = ExternalApiLimiter(
            default_max_concurrency=2,
            by_endpoint={"inventory": 1},
        )
        checker_one = ExternalDataChecker(report, mm, external_api_limiter=limiter)
        checker_two = ExternalDataChecker(report, mm, external_api_limiter=limiter)

        inflight = 0
        max_inflight = 0
        inflight_lock = asyncio.Lock()

        async def controlled_get(*args, **kwargs):
            nonlocal inflight, max_inflight
            async with inflight_lock:
                inflight += 1
                max_inflight = max(max_inflight, inflight)
            await asyncio.sleep(0.05)
            async with inflight_lock:
                inflight -= 1

            mock_resp = Mock()
            mock_resp.json.return_value = {"data": {"devices": ["server1", "server2"]}}
            mock_resp.raise_for_status = Mock()
            return mock_resp

        with patch("report_check.checkers.external.httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(side_effect=controlled_get)

            rule_config = {
                "extract": {
                    "type": "text",
                    "description": "设备列表",
                    "context_hint": "设备相关章节",
                },
                "external_api": {
                    "name": "inventory",
                    "endpoint": "https://api.example.com/devices",
                    "method": "GET",
                    "response_path": "data.devices",
                },
                "analysis": {
                    "requirement": "报告中的设备必须在清单中",
                },
            }

            first, second = await asyncio.gather(
                checker_one.check(rule_config),
                checker_two.check(rule_config),
            )

        assert first.status == "passed"
        assert second.status == "passed"
        assert max_inflight == 1
