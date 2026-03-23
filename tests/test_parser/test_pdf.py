"""PDF 解析器测试"""
from pathlib import Path
import pytest
from report_check.parser.pdf import PDFParser
from report_check.parser.models import ReportData, ContentBlock, ImageData


class TestPDFParser:
    def test_parse_normal_pdf(self):
        """测试解析正常 PDF"""
        parser = PDFParser()
        pdf_path = "tests/fixtures/telecom_report.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"Test file {pdf_path} not found")

        report = parser.parse(pdf_path)
        assert isinstance(report, ReportData)
        assert report.source_type == "pdf"
        assert report.metadata["is_scanned"] is False
        assert len(report.content_blocks) > 0
        assert any(b.content_type == "text" for b in report.content_blocks)

    def test_parse_scanned_pdf(self):
        """测试解析扫描件 PDF"""
        parser = PDFParser()
        pdf_path = "tests/fixtures/telecom_report_scanned.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"Test file {pdf_path} not found")

        report = parser.parse(pdf_path)
        assert isinstance(report, ReportData)
        assert report.source_type == "pdf"
        assert report.metadata["is_scanned"] is True
        assert len(report.images) > 0
        assert all(img.format in ("png", "jpeg", "jpg") for img in report.images)

    def test_detect_scanned_pdf(self):
        """测试扫描件检测"""
        parser = PDFParser()

        normal_pdf = "tests/fixtures/telecom_report.pdf"
        scanned_pdf = "tests/fixtures/telecom_report_scanned.pdf"

        if Path(normal_pdf).exists():
            assert parser._detect_scanned_pdf(normal_pdf) is False

        if Path(scanned_pdf).exists():
            assert parser._detect_scanned_pdf(scanned_pdf) is True

    def test_parse_multipage_scanned(self):
        """测试多页扫描件"""
        parser = PDFParser()
        pdf_path = "tests/fixtures/multipage_scanned.pdf"

        if not Path(pdf_path).exists():
            pytest.skip(f"Test file {pdf_path} not found")

        report = parser.parse(pdf_path)
        assert report.metadata["is_scanned"] is True
        assert report.metadata["page_count"] >= 2
        assert len(report.images) == report.metadata["page_count"]
