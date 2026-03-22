import pytest
from pathlib import Path
from unittest.mock import Mock, AsyncMock

from report_check.parser.excel import ExcelParser
from report_check.parser.models import ReportData
from report_check.models.manager import ModelManager
from report_check.checkers.text import TextChecker


@pytest.fixture
def report_data(sample_excel_path: Path):
    """Create a ReportData instance from sample Excel."""
    parser = ExcelParser()
    return parser.parse(str(sample_excel_path))


@pytest.fixture
def model_manager():
    """Create a mock ModelManager."""
    manager = Mock(spec=ModelManager)
    manager.generate = AsyncMock()
    return manager


@pytest.fixture
def text_checker(report_data, model_manager):
    """Create a TextChecker instance."""
    return TextChecker(report_data, model_manager)


@pytest.mark.asyncio
async def test_keyword_found(text_checker):
    """Test that keyword is found and returns pass status."""
    rule_config = {
        "rule_id": "test_001",
        "rule_name": "Test Keyword Found",
        "rule_type": "text",
        "keywords": ["服务器"],
        "match_mode": "any",
        "case_sensitive": False,
        "min_occurrences": 1,
    }

    result = text_checker.check(rule_config)

    assert result.status == "pass"
    assert result.rule_id == "test_001"
    assert result.rule_name == "Test Keyword Found"
    assert "服务器" in result.message


@pytest.mark.asyncio
async def test_keyword_not_found(text_checker):
    """Test that missing keyword returns error status."""
    rule_config = {
        "rule_id": "test_002",
        "rule_name": "Test Keyword Not Found",
        "rule_type": "text",
        "keywords": ["不存在的关键词"],
        "match_mode": "any",
        "case_sensitive": False,
        "min_occurrences": 1,
    }

    result = text_checker.check(rule_config)

    assert result.status == "error"
    assert result.rule_id == "test_002"
    assert "not found" in result.message.lower() or "找不到" in result.message


@pytest.mark.asyncio
async def test_match_mode_all(text_checker):
    """Test match_mode='all' with all keywords present."""
    rule_config = {
        "rule_id": "test_003",
        "rule_name": "Test All Keywords",
        "rule_type": "text",
        "keywords": ["服务器", "部署"],
        "match_mode": "all",
        "case_sensitive": False,
        "min_occurrences": 1,
    }

    result = text_checker.check(rule_config)

    assert result.status == "pass"
    assert "All required keywords found" in result.message or "all" in result.message.lower()


@pytest.mark.asyncio
async def test_match_mode_all_partial(text_checker):
    """Test match_mode='all' with some keywords missing."""
    rule_config = {
        "rule_id": "test_004",
        "rule_name": "Test All Keywords Partial",
        "rule_type": "text",
        "keywords": ["服务器", "不存在的关键词"],
        "match_mode": "all",
        "case_sensitive": False,
        "min_occurrences": 1,
    }

    result = text_checker.check(rule_config)

    assert result.status == "error"
    assert "不存在的关键词" in result.message or "missing" in result.message.lower()


@pytest.mark.asyncio
async def test_min_occurrences(text_checker):
    """Test min_occurrences requirement."""
    rule_config = {
        "rule_id": "test_005",
        "rule_name": "Test Min Occurrences",
        "rule_type": "text",
        "keywords": ["服务器"],
        "match_mode": "any",
        "case_sensitive": False,
        "min_occurrences": 5,
    }

    result = text_checker.check(rule_config)

    # The keyword appears only once or twice in the sample, so this should fail
    assert result.status == "error"
    assert "occurrence" in result.message.lower() or "occurrences" in result.message.lower()
