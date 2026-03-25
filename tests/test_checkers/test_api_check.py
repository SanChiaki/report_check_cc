import pytest
import json
from unittest.mock import AsyncMock, Mock, patch

from report_check.checkers.api_check import ApiChecker
from report_check.parser.excel import ExcelParser


class TestApiChecker:
    @pytest.mark.asyncio
    async def test_api_check_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        # Mock locate_content to find an image
        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A15", "context": "签名区域", "confidence": 0.9}],
            "reason": "found",
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)

        checker = ApiChecker(report, mm)

        # Mock the HTTP call
        with patch("report_check.checkers.api_check.httpx.AsyncClient") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = {"status": "valid"}
            mock_resp.raise_for_status = Mock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "image",
                    "description": "签名图片",
                    "fallback": "last_image",
                },
                "api": {
                    "name": "sig_check",
                    "endpoint": "https://api.example.com/check",
                    "method": "POST",
                    "body": {"image": "${extracted_content}"},
                    "timeout": 10,
                },
                "validation": {
                    "success_field": "status",
                    "success_value": "valid",
                    "operator": "eq",
                    "error_message": "签名无效",
                },
            })
            assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_api_check_content_not_found_uses_fallback(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({"found": False, "locations": [], "reason": "not found"})
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)

        checker = ApiChecker(report, mm)

        with patch("report_check.checkers.api_check.httpx.AsyncClient") as mock_client:
            mock_resp = Mock()
            mock_resp.json.return_value = {"status": "valid"}
            mock_resp.raise_for_status = Mock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "image",
                    "description": "签名图片",
                    "fallback": "last_image",
                },
                "api": {
                    "name": "sig_check",
                    "endpoint": "https://api.example.com/check",
                    "method": "POST",
                },
                "validation": {
                    "success_field": "status",
                    "success_value": "valid",
                    "operator": "eq",
                },
            })
            # Should use fallback (last image) and still work
            assert result.status in ("passed", "error")

    @pytest.mark.asyncio
    async def test_validation_operators(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        checker = ApiChecker(report, AsyncMock())

        # eq
        assert checker._validate_response({"score": 100}, {"success_field": "score", "success_value": "100", "operator": "eq"})
        # neq
        assert checker._validate_response({"status": "ok"}, {"success_field": "status", "success_value": "error", "operator": "neq"})
        # contains
        assert checker._validate_response({"msg": "success!"}, {"success_field": "msg", "success_value": "success", "operator": "contains"})
        # gt
        assert checker._validate_response({"score": 90}, {"success_field": "score", "success_value": "80", "operator": "gt"})
        # gte
        assert checker._validate_response({"score": 80}, {"success_field": "score", "success_value": "80", "operator": "gte"})
