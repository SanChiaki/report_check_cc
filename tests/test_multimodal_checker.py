"""Test multimodal checker with quality inspection report."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_quality_inspection_report():
    """Test multimodal checker on quality inspection report."""
    from report_check.parser.excel import ExcelParser
    from report_check.checkers.factory import CheckerFactory

    # Parse the quality inspection report
    report_path = Path("/Users/oam/Desktop/一致性检查测试/质检报告/质检报告.xlsx")
    if not report_path.exists():
        pytest.skip("Quality inspection report not found")

    parser = ExcelParser()
    report_data = parser.parse(str(report_path))

    # Mock model manager
    model_manager = MagicMock()
    model_manager.call_multimodal_model = AsyncMock(return_value='''
    {
      "status": "failed",
      "message": "检查发现9个质检项，但只有2个有对应照片",
      "suggestion": "请为配电检查、设备安装检查等缺少照片的质检项补充现场照片",
      "details": {
        "total_items": 9,
        "items_with_photo": 2,
        "items_without_photo": 7
      },
      "confidence": 0.95
    }
    ''')

    # Create multimodal checker
    checker = CheckerFactory.create("multimodal_check", report_data, model_manager)

    # Test rule: check if each quality item has corresponding photo
    rule_config = {
        "rule_id": "qc_photo_check",
        "rule_name": "质检项照片完整性检查",
        "rule_type": "multimodal_check",
        "requirement": "检查报告中的每个质检项（如机柜检查、配电检查等）是否都有对应的现场照片证明",
        "context_hint": "质检项通常在'质检分类'下方列出，照片可能嵌入在表格中",
    }

    result = await checker.check(rule_config)

    # Verify result structure
    assert result.status in ["passed", "failed", "error"]
    assert result.message
    print(f"\nStatus: {result.status}")
    print(f"Message: {result.message}")
    print(f"Confidence: {result.confidence}")

    # Verify model was called
    assert model_manager.call_multimodal_model.called
    print(f"\n多模态模型调用次数: {model_manager.call_multimodal_model.call_count}")


@pytest.mark.asyncio
async def test_multimodal_checker_without_images():
    """Test checker when report has no renderable content."""
    from report_check.checkers.multimodal import MultimodalChecker

    # Create mock report data with no images
    report_data = MagicMock()
    report_data.source_type = "excel"
    report_data.metadata = {"file_path": "/nonexistent.xlsx"}

    model_manager = MagicMock()
    checker = MultimodalChecker(report_data, model_manager)

    result = await checker.check({
        "rule_id": "test",
        "rule_name": "Test",
        "requirement": "test requirement",
    })

    assert result.status == "error"
    assert "无法渲染" in result.message


@pytest.mark.asyncio
async def test_multimodal_checker_parse_response():
    """Test response parsing."""
    from report_check.checkers.multimodal import MultimodalChecker

    checker = MultimodalChecker(None, None)

    # Test valid JSON response
    response = '{"status": "passed", "message": "OK", "confidence": 0.9}'
    result = checker._parse_response(response)
    assert result["status"] == "passed"

    # Test markdown wrapped JSON
    response = '''```json
    {"status": "failed", "message": "Missing", "confidence": 0.8}
    ```'''
    result = checker._parse_response(response)
    assert result["status"] == "failed"

    # Test invalid JSON
    result = checker._parse_response("not json")
    assert result["status"] == "error"


def test_checker_factory_registration():
    """Test that multimodal_check is registered in factory."""
    from report_check.checkers.factory import CheckerFactory
    from report_check.checkers.multimodal import MultimodalChecker

    assert "multimodal_check" in CheckerFactory.CHECKER_MAP
    assert CheckerFactory.CHECKER_MAP["multimodal_check"] == MultimodalChecker
