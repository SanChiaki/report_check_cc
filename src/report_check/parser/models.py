from dataclasses import dataclass, field
from typing import Any


@dataclass
class CellData:
    row: int
    col: int
    value: Any
    cell_ref: str
    data_type: str


@dataclass
class ImageData:
    id: str
    data: bytes
    format: str
    anchor: dict
    nearby_cells: list[CellData] = field(default_factory=list)


@dataclass
class ReportData:
    file_name: str
    sheet_name: str
    cells: list[CellData]
    images: list[ImageData]
    metadata: dict[str, Any]

    def search_text(self, keyword: str, case_sensitive: bool = False) -> list[CellData]:
        results = []
        for cell in self.cells:
            value = str(cell.value)
            if not case_sensitive:
                if keyword.lower() in value.lower():
                    results.append(cell)
            else:
                if keyword in value:
                    results.append(cell)
        return results

    def get_cells_in_range(self, start_row: int, end_row: int,
                           start_col: int, end_col: int) -> list[CellData]:
        return [
            c for c in self.cells
            if start_row <= c.row <= end_row and start_col <= c.col <= end_col
        ]
