"""MSG 解析器测试"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from report_check.parser.msg import MSGParser
from report_check.parser.models import ReportData


@pytest.fixture
def mock_msg():
    """模拟 extract_msg.Message 对象"""
    msg = MagicMock()
    msg.subject = "测试邮件主题"
    msg.sender = "sender@example.com"
    msg.to = "receiver@example.com"
    msg.cc = ""
    msg.date = "2024-01-01 10:00:00"
    msg.body = "这是邮件正文内容，包含一些测试数据。"
    msg.attachments = []
    return msg


@pytest.fixture
def mock_pdf_attachment():
    """模拟 PDF 附件"""
    att = MagicMock()
    att.longFilename = "report.pdf"
    att.shortFilename = "report.pdf"
    return att


@pytest.fixture
def mock_excel_attachment():
    """模拟 Excel 附件"""
    att = MagicMock()
    att.longFilename = "data.xlsx"
    att.shortFilename = "data.xlsx"
    return att


def test_parse_email_body_only(tmp_path, mock_msg):
    """测试仅解析邮件正文（无附件）"""
    msg_file = tmp_path / "test.msg"
    msg_file.write_bytes(b"dummy msg content")

    with patch("extract_msg.Message", return_value=mock_msg):
        parser = MSGParser()
        result = parser.parse(str(msg_file))

    assert isinstance(result, ReportData)
    assert result.source_type == "email"
    assert result.file_name == "test.msg"
    assert len(result.content_blocks) == 1
    assert result.content_blocks[0].content == "这是邮件正文内容，包含一些测试数据。"
    assert result.content_blocks[0].location == "email_body"
    assert result.metadata["subject"] == "测试邮件主题"
    assert result.metadata["sender"] == "sender@example.com"


def test_parse_email_with_pdf_attachment(tmp_path, mock_msg, mock_pdf_attachment):
    """测试解析带 PDF 附件的邮件"""
    msg_file = tmp_path / "test.msg"
    msg_file.write_bytes(b"dummy msg content")

    mock_msg.attachments = [mock_pdf_attachment]

    # 模拟 PDF 解析结果
    mock_pdf_data = ReportData(
        file_name="report.pdf",
        source_type="pdf",
        content_blocks=[],
        images=[],
        metadata={}
    )

    with patch("extract_msg.Message", return_value=mock_msg):
        parser = MSGParser()
        with patch.object(parser.pdf_parser, "parse", return_value=mock_pdf_data):
            result = parser.parse(str(msg_file))

    assert len(result.content_blocks) == 1  # 邮件正文
    assert result.metadata["attachments_count"] == 1


def test_parse_email_with_excel_attachment(tmp_path, mock_msg, mock_excel_attachment):
    """测试解析带 Excel 附件的邮件"""
    msg_file = tmp_path / "test.msg"
    msg_file.write_bytes(b"dummy msg content")

    mock_msg.attachments = [mock_excel_attachment]

    mock_excel_data = ReportData(
        file_name="data.xlsx",
        source_type="excel",
        content_blocks=[],
        images=[],
        metadata={}
    )

    with patch("extract_msg.Message", return_value=mock_msg):
        parser = MSGParser()
        with patch.object(parser.excel_parser, "parse", return_value=mock_excel_data):
            result = parser.parse(str(msg_file))

    assert result.metadata["attachments_count"] == 1

