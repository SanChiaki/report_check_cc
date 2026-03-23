from report_check.parser.models import ReportData


class ReportSummarizer:
    def __init__(self, max_cell_length: int = 200, max_summary_length: int = 4000, max_region_length: int = 8000):
        self.max_cell_length = max_cell_length
        self.max_summary_length = max_summary_length
        self.max_region_length = max_region_length

    def summarize(self, report_data: ReportData) -> str:
        lines: list[str] = []

        # 根据来源类型显示不同的元数据
        if report_data.source_type == "excel":
            sheet_name = report_data.metadata.get("sheet_name", "未知")
            lines.append(f"工作表: {sheet_name}")
            lines.append(f"行数: {report_data.metadata.get('row_count', 0)}, 列数: {report_data.metadata.get('col_count', 0)}")
        elif report_data.source_type == "pdf":
            lines.append(f"PDF 文件: {report_data.file_name}")
            lines.append(f"页数: {report_data.metadata.get('page_count', 0)}")
            is_scanned = report_data.metadata.get('is_scanned', False)
            lines.append(f"类型: {'扫描件' if is_scanned else '正常PDF'}")

        lines.append("")

        # 按位置分组内容块
        if report_data.source_type == "excel":
            # Excel: 按行分组
            rows: dict[int, list] = {}
            for block in report_data.content_blocks:
                row = block.metadata.get("row", 0)
                rows.setdefault(row, []).append(block)

            for row_num in sorted(rows.keys()):
                row_blocks = sorted(rows[row_num], key=lambda b: b.metadata.get("col", 0))
                parts = []
                for block in row_blocks:
                    value = str(block.content)
                    if len(value) > self.max_cell_length:
                        value = value[:self.max_cell_length] + "..."
                    parts.append(f"{block.location}: {value}")
                lines.append(" | ".join(parts))
                current = "\n".join(lines)
                if len(current) >= self.max_summary_length:
                    lines.append("... (内容已截断)")
                    break
        else:
            # PDF: 按页显示
            for block in report_data.content_blocks:
                page = block.metadata.get("page", 0)
                content = str(block.content)
                if len(content) > self.max_cell_length:
                    content = content[:self.max_cell_length] + "..."
                lines.append(f"[{block.location}] {content}")
                current = "\n".join(lines)
                if len(current) >= self.max_summary_length:
                    lines.append("... (内容已截断)")
                    break

        if report_data.images:
            lines.append("")
            lines.append(f"=== 图片 ({len(report_data.images)} 张) ===")
            for img in report_data.images:
                if report_data.source_type == "excel":
                    anchor_ref = img.anchor.get("cell_ref", "未知位置")
                    nearby_text = ", ".join(b.content for b in img.nearby_blocks[:5])
                    lines.append(f"  {img.id} 位置: {anchor_ref}, 附近文字: {nearby_text}")
                else:
                    page = img.anchor.get("page", "未知")
                    lines.append(f"  {img.id} 页码: {page}")

        result = "\n".join(lines)
        if len(result) > self.max_summary_length:
            result = result[:self.max_summary_length] + "\n... (已截断)"
        return result

    def get_region(self, report_data: ReportData, start_row: int, end_row: int) -> str:
        """获取指定区域的内容（仅适用于 Excel）"""
        lines: list[str] = []

        if report_data.source_type != "excel":
            return "get_region 仅支持 Excel 报告"

        rows: dict[int, list] = {}
        for block in report_data.content_blocks:
            row = block.metadata.get("row", 0)
            if start_row <= row <= end_row:
                rows.setdefault(row, []).append(block)

        for row_num in sorted(rows.keys()):
            row_blocks = sorted(rows[row_num], key=lambda b: b.metadata.get("col", 0))
            parts = [f"{b.location}: {b.content}" for b in row_blocks]
            lines.append(" | ".join(parts))

        result = "\n".join(lines)
        if len(result) > self.max_region_length:
            result = result[:self.max_region_length] + "\n... (已截断)"
        return result
