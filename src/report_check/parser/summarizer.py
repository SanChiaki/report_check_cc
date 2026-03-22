from report_check.parser.models import ReportData


class ReportSummarizer:
    def __init__(self, max_cell_length: int = 200, max_summary_length: int = 4000, max_region_length: int = 8000):
        self.max_cell_length = max_cell_length
        self.max_summary_length = max_summary_length
        self.max_region_length = max_region_length

    def summarize(self, report_data: ReportData) -> str:
        lines: list[str] = []
        lines.append(f"工作表: {report_data.sheet_name}")
        lines.append(f"行数: {report_data.metadata.get('row_count', 0)}, 列数: {report_data.metadata.get('col_count', 0)}")
        lines.append("")

        rows: dict[int, list] = {}
        for cell in report_data.cells:
            rows.setdefault(cell.row, []).append(cell)

        for row_num in sorted(rows.keys()):
            row_cells = sorted(rows[row_num], key=lambda c: c.col)
            parts = []
            for cell in row_cells:
                value = str(cell.value)
                if len(value) > self.max_cell_length:
                    value = value[:self.max_cell_length] + "..."
                parts.append(f"{cell.cell_ref}: {value}")
            lines.append(" | ".join(parts))
            current = "\n".join(lines)
            if len(current) >= self.max_summary_length:
                lines.append("... (内容已截断)")
                break

        if report_data.images:
            lines.append("")
            lines.append(f"=== 图片 ({len(report_data.images)} 张) ===")
            for img in report_data.images:
                anchor_ref = img.anchor.get("cell_ref", "未知位置")
                nearby_text = ", ".join(c.value for c in img.nearby_cells[:5])
                lines.append(f"  {img.id} 位置: {anchor_ref}, 附近文字: {nearby_text}")

        result = "\n".join(lines)
        if len(result) > self.max_summary_length:
            result = result[:self.max_summary_length] + "\n... (已截断)"
        return result

    def get_region(self, report_data: ReportData, start_row: int, end_row: int) -> str:
        lines: list[str] = []
        rows: dict[int, list] = {}
        for cell in report_data.cells:
            if start_row <= cell.row <= end_row:
                rows.setdefault(cell.row, []).append(cell)
        for row_num in sorted(rows.keys()):
            row_cells = sorted(rows[row_num], key=lambda c: c.col)
            parts = [f"{c.cell_ref}: {c.value}" for c in row_cells]
            lines.append(" | ".join(parts))
        result = "\n".join(lines)
        if len(result) > self.max_region_length:
            result = result[:self.max_region_length] + "\n... (已截断)"
        return result
