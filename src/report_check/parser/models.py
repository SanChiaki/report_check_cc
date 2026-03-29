from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ContentBlock:
    """通用内容块，支持 Excel 单元格和 PDF 文本块"""
    content: Any
    location: str
    content_type: Literal["text", "number", "date", "image"]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageData:
    id: str
    data: bytes
    format: str
    anchor: dict
    nearby_blocks: list[ContentBlock] = field(default_factory=list)


@dataclass
class ReportData:
    file_name: str
    source_type: Literal["excel", "pdf", "email"]
    content_blocks: list[ContentBlock]
    images: list[ImageData]
    metadata: dict[str, Any]

    def search_text(self, keyword: str, case_sensitive: bool = False) -> list[ContentBlock]:
        results = []
        for block in self.content_blocks:
            if block.content_type in ("text", "number", "date"):
                value = str(block.content)
                if not case_sensitive:
                    if keyword.lower() in value.lower():
                        results.append(block)
                else:
                    if keyword in value:
                        results.append(block)
        return results

    def get_blocks_by_location(self, location_pattern: str) -> list[ContentBlock]:
        """根据位置模式筛选内容块（支持 Excel 范围或 PDF 页码）"""
        return [b for b in self.content_blocks if location_pattern in b.location]
