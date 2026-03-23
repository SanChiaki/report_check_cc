from pathlib import Path
from report_check.parser.excel import ExcelParser
from report_check.parser.models import ReportData, ContentBlock, ImageData


class TestExcelParser:
    def test_parse_extracts_cells(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        assert isinstance(report, ReportData)
        assert report.metadata["sheet_name"] == "报告"
        assert len(report.content_blocks) > 0
        a1_blocks = [b for b in report.content_blocks if b.location == "A1"]
        assert len(a1_blocks) == 1
        assert a1_blocks[0].content == "交付报告"

    def test_parse_extracts_images(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        assert len(report.images) >= 1
        img = report.images[0]
        assert isinstance(img, ImageData)
        assert img.format in ("png", "jpeg", "PNG", "JPEG")
        assert len(img.data) > 0

    def test_parse_image_nearby_cells(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        img = report.images[0]
        assert len(img.nearby_blocks) > 0

    def test_parse_no_images(self, sample_excel_no_images: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))
        assert len(report.images) == 0
        assert len(report.content_blocks) > 0

    def test_parse_metadata(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        assert "row_count" in report.metadata
        assert "col_count" in report.metadata
        assert report.metadata["row_count"] > 0


class TestReportDataSearch:
    def test_search_text_found(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        results = report.search_text("交付内容")
        assert len(results) >= 1
        assert any(b.content == "交付内容" for b in results)

    def test_search_text_not_found(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        results = report.search_text("不存在的内容")
        assert len(results) == 0

    def test_search_text_case_insensitive(self, sample_excel_no_images: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))
        results = report.search_text("交付内容", case_sensitive=False)
        assert len(results) >= 1
