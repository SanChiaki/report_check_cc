from report_check.parser.excel import ExcelParser
from report_check.parser.summarizer import ReportSummarizer


class TestReportSummarizer:
    def test_summarize_returns_string(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        summarizer = ReportSummarizer()
        result = summarizer.summarize(report)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_summarize_contains_cell_content(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        summarizer = ReportSummarizer()
        result = summarizer.summarize(report)
        assert "交付报告" in result
        assert "交付内容" in result

    def test_summarize_respects_max_length(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        summarizer = ReportSummarizer(max_summary_length=100)
        result = summarizer.summarize(report)
        assert len(result) <= 200

    def test_summarize_truncates_long_cells(self, sample_excel_no_images):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))
        summarizer = ReportSummarizer(max_cell_length=5)
        result = summarizer.summarize(report)
        assert isinstance(result, str)

    def test_summarize_includes_image_info(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        summarizer = ReportSummarizer()
        result = summarizer.summarize(report)
        assert "图片" in result or "img" in result.lower()

    def test_get_region(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        summarizer = ReportSummarizer()
        result = summarizer.get_region(report, start_row=10, end_row=13)
        assert "移交记录" in result or "移交人" in result
