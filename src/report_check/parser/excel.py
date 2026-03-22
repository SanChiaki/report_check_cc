import logging
from io import BytesIO
from pathlib import Path
import openpyxl
from openpyxl.utils import get_column_letter
from PIL import Image
from report_check.parser.models import CellData, ImageData, ReportData

logger = logging.getLogger(__name__)
NEARBY_RADIUS = 3
MAX_IMAGE_SIZE = 2048


class ExcelParser:
    def parse(self, file_path: str) -> ReportData:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        cells = self._extract_cells(ws)
        images = self._extract_images(ws)
        return ReportData(
            file_name=Path(file_path).name,
            sheet_name=ws.title,
            cells=cells,
            images=images,
            metadata={"row_count": ws.max_row or 0, "col_count": ws.max_column or 0},
        )

    def _extract_cells(self, ws) -> list[CellData]:
        cells = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells.append(CellData(
                        row=cell.row, col=cell.column,
                        value=str(cell.value), cell_ref=cell.coordinate,
                        data_type=cell.data_type or "s",
                    ))
        return cells

    def _extract_images(self, ws) -> list[ImageData]:
        images = []
        for i, img in enumerate(ws._images):
            try:
                image_data = self._get_image_bytes(img)
                if image_data is None:
                    continue
                fmt = self._detect_and_convert_format(image_data)
                if fmt is None:
                    continue
                anchor = self._get_anchor(img)
                nearby = self._get_nearby_cells(ws, anchor.get("row", 1), anchor.get("col", 1))
                images.append(ImageData(
                    id=f"img_{i}",
                    data=image_data if fmt[1] is None else fmt[1],
                    format=fmt[0], anchor=anchor, nearby_cells=nearby,
                ))
            except Exception as e:
                logger.warning(f"Failed to extract image {i}: {e}")
        return images

    def _get_image_bytes(self, img) -> bytes | None:
        try:
            if hasattr(img, "_data"):
                return img._data()
            if hasattr(img, "ref"):
                with open(img.ref, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Cannot read image data: {e}")
        return None

    def _detect_and_convert_format(self, data: bytes) -> tuple[str, bytes | None] | None:
        try:
            pil_img = Image.open(BytesIO(data))
        except Exception:
            return None
        fmt = (pil_img.format or "PNG").lower()
        if max(pil_img.size) > MAX_IMAGE_SIZE:
            pil_img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            return ("png", buf.getvalue())
        if fmt not in ("png", "jpeg", "jpg", "gif", "webp"):
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            return ("png", buf.getvalue())
        return (fmt, None)

    def _get_anchor(self, img) -> dict:
        anchor = {}
        try:
            if hasattr(img.anchor, "_from"):
                anchor_cell = img.anchor._from
                row = anchor_cell.row + 1
                col = anchor_cell.col + 1
                anchor = {"row": row, "col": col, "cell_ref": f"{get_column_letter(col)}{row}"}
            elif isinstance(img.anchor, str):
                from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
                col_letter, row = coordinate_from_string(img.anchor)
                col = column_index_from_string(col_letter)
                anchor = {"row": row, "col": col, "cell_ref": img.anchor}
        except Exception as e:
            logger.warning(f"Cannot parse anchor: {e}")
            anchor = {"row": 1, "col": 1, "cell_ref": "A1"}
        return anchor

    def _get_nearby_cells(self, ws, row: int, col: int) -> list[CellData]:
        nearby = []
        for r in range(max(1, row - NEARBY_RADIUS), min((ws.max_row or 1) + 1, row + NEARBY_RADIUS + 1)):
            for c in range(max(1, col - NEARBY_RADIUS), min((ws.max_column or 1) + 1, col + NEARBY_RADIUS + 1)):
                cell = ws.cell(r, c)
                if cell.value is not None:
                    nearby.append(CellData(
                        row=r, col=c, value=str(cell.value),
                        cell_ref=cell.coordinate, data_type=cell.data_type or "s",
                    ))
        return nearby
