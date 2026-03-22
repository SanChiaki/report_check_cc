# 报告一致性检查系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an AI-powered Excel report consistency checking system with semantic rule DSL, pluggable checkers, multi-model support, and async task processing.

**Architecture:** FastAPI backend with pluggable checker pattern. Excel reports are parsed into structured data, then each rule in the DSL drives a checker (text/semantic/image/API/external) that uses AI to locate and validate content. Tasks are queued and processed asynchronously with results stored in SQLite.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, openpyxl, Pillow, openai SDK, httpx, aiosqlite, SQLite, uv, Docker

**Spec:** `docs/superpowers/specs/2026-03-22-report-consistency-check-design.md`

---

## File Structure

```
report_check/
├── pyproject.toml
├── config/
│   ├── models.yaml
│   └── app.yaml
├── src/
│   └── report_check/
│       ├── __init__.py
│       ├── main.py                    # FastAPI app entry, lifespan, CORS
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py              # Load YAML config, env vars
│       │   └── exceptions.py          # CheckError, RuleValidationError, etc.
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py              # All route definitions
│       │   └── schemas.py             # Pydantic request/response models
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── excel.py               # ExcelParser: cells + images extraction
│       │   ├── models.py              # CellData, ImageData, ReportData dataclasses
│       │   └── summarizer.py          # ReportSummarizer: token-optimized text
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── rule_engine.py         # RuleEngine: parse, merge, iterate rules
│       │   ├── validator.py           # RuleValidator: DSL schema validation
│       │   └── variable_resolver.py   # Resolve ${var} in rule configs
│       ├── checkers/
│       │   ├── __init__.py
│       │   ├── base.py                # BaseChecker, CheckResult, locate_content
│       │   ├── factory.py             # CheckerFactory
│       │   ├── text.py                # TextChecker
│       │   ├── semantic.py            # SemanticChecker
│       │   ├── image.py               # ImageChecker
│       │   ├── api_check.py           # ApiChecker
│       │   └── external.py            # ExternalDataChecker
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py                # BaseModelAdapter ABC
│       │   ├── manager.py             # ModelManager
│       │   ├── openai_adapter.py      # OpenAIAdapter
│       │   └── qwen_adapter.py        # QwenAdapter
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py            # Database: SQLite access layer
│       │   ├── file.py                # FileStorage: upload management
│       │   └── cache.py               # ResultCache: image check caching
│       └── worker/
│           ├── __init__.py
│           ├── queue.py               # TaskQueue: asyncio.Queue wrapper
│           └── worker.py              # BackgroundWorker: task processing loop
└── tests/
    ├── conftest.py                    # Shared fixtures, test Excel files
    ├── test_parser/
    │   ├── test_excel.py
    │   └── test_summarizer.py
    ├── test_engine/
    │   ├── test_rule_engine.py
    │   ├── test_validator.py
    │   └── test_variable_resolver.py
    ├── test_checkers/
    │   ├── test_text.py
    │   ├── test_semantic.py
    │   ├── test_image.py
    │   ├── test_api_check.py
    │   └── test_external.py
    ├── test_models/
    │   └── test_manager.py
    ├── test_storage/
    │   └── test_database.py
    └── test_api/
        └── test_router.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/report_check/__init__.py`
- Create: `src/report_check/core/__init__.py`
- Create: `config/models.yaml`
- Create: `config/app.yaml`

- [ ] **Step 1: Initialize project with uv**

```bash
uv init --lib --name report_check
```

- [ ] **Step 2: Configure pyproject.toml**

```toml
[project]
name = "report-check"
version = "0.1.0"
description = "AI-powered Excel report consistency checking system"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0.0",
    "openpyxl>=3.1.0",
    "pillow>=10.0.0",
    "openai>=1.0.0",
    "httpx>=0.27.0",
    "pyyaml>=6.0",
    "python-multipart>=0.0.9",
    "aiosqlite>=0.20.0",
    "slowapi>=0.1.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[tool.hatch.build.targets.wheel]
packages = ["src/report_check"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 3: Install dependencies**

```bash
uv sync
```

- [ ] **Step 4: Create config files**

`config/models.yaml`:
```yaml
default_provider: openai

providers:
  openai:
    api_key: ${OPENAI_API_KEY}
    text_model: gpt-4o
    multimodal_model: gpt-4o
    base_url: https://api.openai.com/v1

  qwen:
    base_url: http://internal-qwen-api:8000
    api_key: ${QWEN_API_KEY}
    text_model: qwen-turbo
    multimodal_model: qwen-vl-plus
```

`config/app.yaml`:
```yaml
server:
  host: "0.0.0.0"
  port: 8000

storage:
  database_path: "data/reports.db"
  upload_path: "data/uploads"

limits:
  max_file_size_mb: 20
  max_cells: 50000
  max_images: 50
  rate_limit: "10/minute"

summarizer:
  max_cell_length: 200
  max_summary_length: 4000
  max_region_length: 8000
```

- [ ] **Step 5: Create package __init__.py files**

Create empty `__init__.py` in: `src/report_check/`, `src/report_check/core/`, `src/report_check/api/`, `src/report_check/parser/`, `src/report_check/engine/`, `src/report_check/checkers/`, `src/report_check/models/`, `src/report_check/storage/`, `src/report_check/worker/`

- [ ] **Step 6: Create core config loader**

`src/report_check/core/config.py`:
```python
import os
from pathlib import Path
from typing import Any

import yaml


def _resolve_env_vars(obj: Any) -> Any:
    """Recursively resolve ${ENV_VAR} in config values."""
    if isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        return os.environ.get(var_name, "")
    elif isinstance(obj, dict):
        return {k: _resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_resolve_env_vars(item) for item in obj]
    return obj


def load_config(path: str) -> dict:
    """Load YAML config file with environment variable resolution."""
    with open(path, "r") as f:
        raw = yaml.safe_load(f)
    return _resolve_env_vars(raw)
```

- [ ] **Step 7: Create custom exceptions**

`src/report_check/core/exceptions.py`:
```python
class CheckError(Exception):
    """Base error for the checking system."""
    def __init__(self, message: str, code: str = "CHECK_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class RuleValidationError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "RULE_VALIDATION_ERROR")


class ExcelParseError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "EXCEL_PARSE_ERROR")


class ModelError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "MODEL_ERROR")


class FileTooLargeError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "FILE_TOO_LARGE")


class FileFormatError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "FILE_FORMAT_ERROR")


class VariableMissingError(CheckError):
    def __init__(self, message: str):
        super().__init__(message, "VARIABLE_MISSING")
```

- [ ] **Step 8: Verify project structure**

```bash
uv run python -c "from report_check.core.config import load_config; print('OK')"
```

Expected: `OK`

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: project scaffolding with config and exceptions"
```

---

### Task 2: Data Models & Excel Parser

**Files:**
- Create: `src/report_check/parser/models.py`
- Create: `src/report_check/parser/excel.py`
- Create: `src/report_check/parser/__init__.py`
- Test: `tests/test_parser/test_excel.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write parser data models**

`src/report_check/parser/models.py`:
```python
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
        """Search cells containing keyword."""
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
        """Get cells within a row/col range."""
        return [
            c for c in self.cells
            if start_row <= c.row <= end_row and start_col <= c.col <= end_col
        ]
```

- [ ] **Step 2: Create test fixture — a sample Excel file**

`tests/conftest.py`:
```python
import pytest
from pathlib import Path
import openpyxl
from PIL import Image
from io import BytesIO


@pytest.fixture
def sample_excel_path(tmp_path: Path) -> Path:
    """Create a sample Excel file for testing."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "报告"

    # Header area
    ws["A1"] = "交付报告"
    ws["A2"] = "项目名称"
    ws["B2"] = "XXX服务器部署项目"
    ws["A3"] = "报告日期"
    ws["B3"] = "2026-03-22"

    # Content area
    ws["A5"] = "交付内容"
    ws["A6"] = "1. 服务器部署"
    ws["A7"] = "2. 网络配置"

    # Handover section
    ws["A10"] = "移交记录"
    ws["A11"] = "移交人"
    ws["B11"] = "张三"
    ws["A12"] = "移交时间"
    ws["B12"] = "2026-03-20"
    ws["A13"] = "移交命令"
    ws["B13"] = "deploy --all"

    # Add a small test image
    img = Image.new("RGB", (100, 100), color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    xl_img = openpyxl.drawing.image.Image(buf)
    xl_img.anchor = "A15"
    ws.add_image(xl_img)

    path = tmp_path / "test_report.xlsx"
    wb.save(path)
    return path


@pytest.fixture
def sample_excel_no_images(tmp_path: Path) -> Path:
    """Create a sample Excel file without images."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "简单报告"
    ws["A1"] = "交付内容"
    ws["A2"] = "测试数据"
    path = tmp_path / "simple_report.xlsx"
    wb.save(path)
    return path
```

- [ ] **Step 3: Write failing test for ExcelParser**

`tests/test_parser/test_excel.py`:
```python
from pathlib import Path

from report_check.parser.excel import ExcelParser
from report_check.parser.models import ReportData, CellData, ImageData


class TestExcelParser:
    def test_parse_extracts_cells(self, sample_excel_path: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        assert isinstance(report, ReportData)
        assert report.sheet_name == "报告"
        assert len(report.cells) > 0

        # Check specific cell
        a1_cells = [c for c in report.cells if c.cell_ref == "A1"]
        assert len(a1_cells) == 1
        assert a1_cells[0].value == "交付报告"

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
        # Image is at A15, nearby cells should include rows 12-18
        assert len(img.nearby_cells) > 0

    def test_parse_no_images(self, sample_excel_no_images: Path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))

        assert len(report.images) == 0
        assert len(report.cells) > 0

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
        assert any(c.value == "交付内容" for c in results)

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
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/test_parser/test_excel.py -v
```

Expected: FAIL (ExcelParser not implemented)

- [ ] **Step 5: Implement ExcelParser**

`src/report_check/parser/excel.py`:
```python
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
    """Parse Excel files into structured ReportData."""

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
            metadata={
                "row_count": ws.max_row or 0,
                "col_count": ws.max_column or 0,
            },
        )

    def _extract_cells(self, ws) -> list[CellData]:
        cells = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    cells.append(
                        CellData(
                            row=cell.row,
                            col=cell.column,
                            value=str(cell.value),
                            cell_ref=cell.coordinate,
                            data_type=cell.data_type or "s",
                        )
                    )
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
                nearby = self._get_nearby_cells(
                    ws,
                    anchor.get("row", 1),
                    anchor.get("col", 1),
                )

                images.append(
                    ImageData(
                        id=f"img_{i}",
                        data=image_data if fmt[1] is None else fmt[1],
                        format=fmt[0],
                        anchor=anchor,
                        nearby_cells=nearby,
                    )
                )
            except Exception as e:
                logger.warning(f"Failed to extract image {i}: {e}")

        return images

    def _get_image_bytes(self, img) -> bytes | None:
        """Extract raw image bytes from openpyxl image object."""
        try:
            if hasattr(img, "_data"):
                return img._data()
            if hasattr(img, "ref"):
                with open(img.ref, "rb") as f:
                    return f.read()
        except Exception as e:
            logger.warning(f"Cannot read image data: {e}")
        return None

    def _detect_and_convert_format(
        self, data: bytes
    ) -> tuple[str, bytes | None] | None:
        """Detect image format. Convert non-standard formats to PNG.

        Returns (format_name, converted_bytes_or_None). None if conversion fails.
        """
        try:
            pil_img = Image.open(BytesIO(data))
        except Exception:
            logger.warning("Cannot open image with Pillow, skipping")
            return None

        fmt = (pil_img.format or "PNG").lower()

        # Resize if too large
        if max(pil_img.size) > MAX_IMAGE_SIZE:
            pil_img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            return ("png", buf.getvalue())

        # Convert non-standard formats
        if fmt not in ("png", "jpeg", "jpg", "gif", "webp"):
            buf = BytesIO()
            pil_img.save(buf, format="PNG")
            return ("png", buf.getvalue())

        return (fmt, None)

    def _get_anchor(self, img) -> dict:
        """Extract anchor position from image."""
        anchor = {}
        try:
            if hasattr(img.anchor, "_from"):
                anchor_cell = img.anchor._from
                row = anchor_cell.row + 1
                col = anchor_cell.col + 1
                anchor = {
                    "row": row,
                    "col": col,
                    "cell_ref": f"{get_column_letter(col)}{row}",
                }
            elif isinstance(img.anchor, str):
                # Simple anchor like "A15"
                from openpyxl.utils.cell import coordinate_from_string, column_index_from_string
                col_letter, row = coordinate_from_string(img.anchor)
                col = column_index_from_string(col_letter)
                anchor = {
                    "row": row,
                    "col": col,
                    "cell_ref": img.anchor,
                }
        except Exception as e:
            logger.warning(f"Cannot parse anchor: {e}")
            anchor = {"row": 1, "col": 1, "cell_ref": "A1"}
        return anchor

    def _get_nearby_cells(self, ws, row: int, col: int) -> list[CellData]:
        """Get non-empty cells within NEARBY_RADIUS of the given position."""
        nearby = []
        for r in range(
            max(1, row - NEARBY_RADIUS),
            min((ws.max_row or 1) + 1, row + NEARBY_RADIUS + 1),
        ):
            for c in range(
                max(1, col - NEARBY_RADIUS),
                min((ws.max_column or 1) + 1, col + NEARBY_RADIUS + 1),
            ):
                cell = ws.cell(r, c)
                if cell.value is not None:
                    nearby.append(
                        CellData(
                            row=r,
                            col=c,
                            value=str(cell.value),
                            cell_ref=cell.coordinate,
                            data_type=cell.data_type or "s",
                        )
                    )
        return nearby
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_parser/test_excel.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/report_check/parser/ tests/conftest.py tests/test_parser/
git commit -m "feat: Excel parser with cell and image extraction"
```

---

### Task 3: Report Summarizer

**Files:**
- Create: `src/report_check/parser/summarizer.py`
- Test: `tests/test_parser/test_summarizer.py`

- [ ] **Step 1: Write failing test for ReportSummarizer**

`tests/test_parser/test_summarizer.py`:
```python
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
        assert len(result) <= 200  # Allow some overflow for truncation markers

    def test_summarize_truncates_long_cells(self, sample_excel_no_images):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))
        summarizer = ReportSummarizer(max_cell_length=5)

        result = summarizer.summarize(report)
        # "交付内容" is 4 chars, should not be truncated
        # But longer content should be
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_parser/test_summarizer.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement ReportSummarizer**

`src/report_check/parser/summarizer.py`:
```python
from report_check.parser.models import ReportData


class ReportSummarizer:
    """Generate token-optimized text summaries of report data for AI consumption."""

    def __init__(
        self,
        max_cell_length: int = 200,
        max_summary_length: int = 4000,
        max_region_length: int = 8000,
    ):
        self.max_cell_length = max_cell_length
        self.max_summary_length = max_summary_length
        self.max_region_length = max_region_length

    def summarize(self, report_data: ReportData) -> str:
        """Generate a compressed summary of the entire report."""
        lines: list[str] = []
        lines.append(f"工作表: {report_data.sheet_name}")
        lines.append(
            f"行数: {report_data.metadata.get('row_count', 0)}, "
            f"列数: {report_data.metadata.get('col_count', 0)}"
        )
        lines.append("")

        # Group cells by row
        rows: dict[int, list] = {}
        for cell in report_data.cells:
            rows.setdefault(cell.row, []).append(cell)

        for row_num in sorted(rows.keys()):
            row_cells = sorted(rows[row_num], key=lambda c: c.col)
            parts = []
            for cell in row_cells:
                value = str(cell.value)
                if len(value) > self.max_cell_length:
                    value = value[: self.max_cell_length] + "..."
                parts.append(f"{cell.cell_ref}: {value}")
            lines.append(" | ".join(parts))

            # Check length limit
            current = "\n".join(lines)
            if len(current) >= self.max_summary_length:
                lines.append("... (内容已截断)")
                break

        # Image info
        if report_data.images:
            lines.append("")
            lines.append(f"=== 图片 ({len(report_data.images)} 张) ===")
            for img in report_data.images:
                anchor_ref = img.anchor.get("cell_ref", "未知位置")
                nearby_text = ", ".join(
                    c.value for c in img.nearby_cells[:5]
                )
                lines.append(f"  {img.id} 位置: {anchor_ref}, 附近文字: {nearby_text}")

        result = "\n".join(lines)
        if len(result) > self.max_summary_length:
            result = result[: self.max_summary_length] + "\n... (已截断)"
        return result

    def get_region(
        self, report_data: ReportData, start_row: int, end_row: int
    ) -> str:
        """Get full content of a specific row range (for verification phase)."""
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
            result = result[: self.max_region_length] + "\n... (已截断)"
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_parser/test_summarizer.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/report_check/parser/summarizer.py tests/test_parser/test_summarizer.py
git commit -m "feat: report summarizer with token optimization"
```

---

### Task 4: Storage Layer (Database + FileStorage + Cache)

**Files:**
- Create: `src/report_check/storage/database.py`
- Create: `src/report_check/storage/file.py`
- Create: `src/report_check/storage/cache.py`
- Test: `tests/test_storage/test_database.py`

- [ ] **Step 1: Write failing test for Database**

`tests/test_storage/test_database.py`:
```python
import pytest
from pathlib import Path
from datetime import datetime

from report_check.storage.database import Database, TaskStatus


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


class TestDatabase:
    @pytest.mark.asyncio
    async def test_create_and_get_task(self, db: Database):
        task_id = await db.create_task(
            task_id="test-001",
            file_name="report.xlsx",
            file_path="/tmp/report.xlsx",
            rules={"rules": []},
            report_type="server",
        )
        assert task_id == "test-001"

        task = await db.get_task("test-001")
        assert task is not None
        assert task["file_name"] == "report.xlsx"
        assert task["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, db: Database):
        task = await db.get_task("nonexistent")
        assert task is None

    @pytest.mark.asyncio
    async def test_update_task_status(self, db: Database):
        await db.create_task(
            task_id="test-002",
            file_name="r.xlsx",
            file_path="/tmp/r.xlsx",
            rules={"rules": []},
        )
        await db.update_task_status("test-002", TaskStatus.PROCESSING)
        task = await db.get_task("test-002")
        assert task["status"] == "processing"

    @pytest.mark.asyncio
    async def test_update_task_progress(self, db: Database):
        await db.create_task(
            task_id="test-003",
            file_name="r.xlsx",
            file_path="/tmp/r.xlsx",
            rules={"rules": []},
        )
        await db.update_task_progress("test-003", 50)
        task = await db.get_task("test-003")
        assert task["progress"] == 50

    @pytest.mark.asyncio
    async def test_save_and_get_check_results(self, db: Database):
        await db.create_task(
            task_id="test-004",
            file_name="r.xlsx",
            file_path="/tmp/r.xlsx",
            rules={"rules": []},
        )
        await db.save_check_results("test-004", [
            {
                "rule_id": "rule_001",
                "rule_name": "检查交付内容",
                "rule_type": "text",
                "status": "passed",
                "location": {"type": "cell_range", "value": "A5"},
                "message": "找到关键词",
                "suggestion": "",
                "example": "",
                "confidence": 1.0,
                "execution_time": 0.1,
            }
        ])
        results = await db.get_check_results("test-004")
        assert len(results) == 1
        assert results[0]["rule_id"] == "rule_001"

    @pytest.mark.asyncio
    async def test_delete_check_results(self, db: Database):
        await db.create_task(
            task_id="test-005",
            file_name="r.xlsx",
            file_path="/tmp/r.xlsx",
            rules={"rules": []},
        )
        await db.save_check_results("test-005", [
            {
                "rule_id": "r1",
                "rule_name": "test",
                "rule_type": "text",
                "status": "passed",
                "location": {},
                "message": "",
                "suggestion": "",
                "example": "",
                "confidence": 1.0,
                "execution_time": 0.1,
            }
        ])
        await db.delete_check_results("test-005")
        results = await db.get_check_results("test-005")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_recover_orphaned_tasks(self, db: Database):
        await db.create_task(
            task_id="orphan-001",
            file_name="r.xlsx",
            file_path="/tmp/r.xlsx",
            rules={"rules": []},
        )
        await db.update_task_status("orphan-001", TaskStatus.PROCESSING)

        task_ids = await db.recover_orphaned_tasks()
        assert "orphan-001" in task_ids

        task = await db.get_task("orphan-001")
        assert task["status"] == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_storage/test_database.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement Database**

`src/report_check/storage/database.py`:
```python
import json
import sqlite3
from enum import Enum
from typing import Any

import aiosqlite


class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Database:
    """Async SQLite data access layer using aiosqlite."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db_sync()

    def _init_db_sync(self):
        """Synchronous init for table creation (called once at startup)."""
        conn = sqlite3.connect(self.db_path)
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                rules TEXT NOT NULL,
                report_type TEXT,
                context_vars TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                progress INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                started_at TIMESTAMP,
                completed_at TIMESTAMP,
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS check_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                rule_type TEXT NOT NULL,
                status TEXT NOT NULL,
                location TEXT,
                message TEXT,
                suggestion TEXT,
                example TEXT,
                confidence REAL,
                execution_time REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (task_id) REFERENCES tasks(task_id)
            );

            CREATE TABLE IF NOT EXISTS rule_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                description TEXT,
                rules TEXT NOT NULL,
                version TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at);
            CREATE INDEX IF NOT EXISTS idx_check_results_task_id ON check_results(task_id);
        """)
        conn.close()

    async def create_task(
        self,
        task_id: str,
        file_name: str,
        file_path: str,
        rules: dict,
        report_type: str | None = None,
        context_vars: dict | None = None,
    ) -> str:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute(
                """INSERT INTO tasks (task_id, file_name, file_path, rules, report_type, context_vars, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (task_id, file_name, file_path, json.dumps(rules), report_type,
                 json.dumps(context_vars) if context_vars else None, "pending"),
            )
            await db.commit()
        return task_id

    async def get_task(self, task_id: str) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    d = dict(row)
                    d["rules"] = json.loads(d["rules"])
                    d["context_vars"] = json.loads(d["context_vars"]) if d.get("context_vars") else {}
                    return d
        return None

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
    ):
        async with aiosqlite.connect(self.db_path) as db:
            if status == TaskStatus.PROCESSING:
                await db.execute(
                    "UPDATE tasks SET status = ?, started_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                    (status.value, task_id),
                )
            elif status == TaskStatus.COMPLETED:
                await db.execute(
                    "UPDATE tasks SET status = ?, progress = 100, completed_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                    (status.value, task_id),
                )
            elif status == TaskStatus.FAILED:
                await db.execute(
                    "UPDATE tasks SET status = ?, error = ?, completed_at = CURRENT_TIMESTAMP WHERE task_id = ?",
                    (status.value, error, task_id),
                )
            else:
                await db.execute(
                    "UPDATE tasks SET status = ? WHERE task_id = ?",
                    (status.value, task_id),
                )
            await db.commit()

    async def update_task_progress(self, task_id: str, progress: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE tasks SET progress = ? WHERE task_id = ?",
                (progress, task_id),
            )
            await db.commit()

    async def save_check_results(self, task_id: str, results: list[dict]):
        async with aiosqlite.connect(self.db_path) as db:
            for r in results:
                await db.execute(
                    """INSERT INTO check_results
                       (task_id, rule_id, rule_name, rule_type, status,
                        location, message, suggestion, example, confidence, execution_time)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        r["rule_id"],
                        r["rule_name"],
                        r["rule_type"],
                        r["status"],
                        json.dumps(r.get("location", {})),
                        r.get("message", ""),
                        r.get("suggestion", ""),
                        r.get("example", ""),
                        r.get("confidence", 1.0),
                        r.get("execution_time", 0.0),
                    ),
                )
            await db.commit()

    async def get_check_results(self, task_id: str) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM check_results WHERE task_id = ? ORDER BY id",
                (task_id,),
            ) as cursor:
                rows = await cursor.fetchall()
                results = []
                for row in rows:
                    d = dict(row)
                    d["location"] = json.loads(d["location"]) if d["location"] else {}
                    results.append(d)
                return results

    async def delete_check_results(self, task_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "DELETE FROM check_results WHERE task_id = ?", (task_id,)
            )
            await db.commit()

    async def recover_orphaned_tasks(self) -> list[str]:
        """Reset processing/pending tasks on startup. Returns task_ids to re-enqueue."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT task_id FROM tasks WHERE status IN ('processing', 'pending')"
            ) as cursor:
                rows = await cursor.fetchall()
                task_ids = [row["task_id"] for row in rows]

            await db.execute(
                "DELETE FROM check_results WHERE task_id IN "
                "(SELECT task_id FROM tasks WHERE status = 'processing')"
            )
            await db.execute(
                "UPDATE tasks SET status = 'pending', progress = 0, started_at = NULL "
                "WHERE status IN ('processing', 'pending')"
            )
            await db.commit()
            return task_ids

    async def get_rule_templates(self, report_type: str | None = None) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            if report_type:
                sql = "SELECT * FROM rule_templates WHERE report_type = ? ORDER BY id"
                async with db.execute(sql, (report_type,)) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with db.execute("SELECT * FROM rule_templates ORDER BY id") as cursor:
                    rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_rule_template(self, template_id: int) -> dict | None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM rule_templates WHERE id = ?", (template_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    d = dict(row)
                    d["rules"] = json.loads(d["rules"])
                    return d
        return None
```

- [ ] **Step 4: Implement FileStorage and ResultCache**

`src/report_check/storage/file.py`:
```python
import uuid
from pathlib import Path


class FileStorage:
    """Manage uploaded file storage."""

    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save_uploaded_file(
        self, file_data: bytes, filename: str, task_id: str
    ) -> str:
        task_dir = self.base_path / task_id
        task_dir.mkdir(exist_ok=True)
        file_path = task_dir / filename
        file_path.write_bytes(file_data)
        return str(file_path)

    async def cleanup_task_files(self, task_id: str):
        import shutil
        task_dir = self.base_path / task_id
        if task_dir.exists():
            shutil.rmtree(task_dir)
```

`src/report_check/storage/cache.py`:
```python
import hashlib


class ResultCache:
    """In-memory cache for image check results."""

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get_cache_key(self, image_data: bytes, requirement: str) -> str:
        image_hash = hashlib.md5(image_data).hexdigest()
        req_hash = hashlib.md5(requirement.encode()).hexdigest()
        return f"{image_hash}:{req_hash}"

    def get(self, key: str) -> dict | None:
        return self._cache.get(key)

    def set(self, key: str, value: dict):
        self._cache[key] = value

    def clear(self):
        self._cache.clear()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_storage/test_database.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/report_check/storage/ tests/test_storage/
git commit -m "feat: storage layer with database, file storage, and cache"
```

---

### Task 5: AI Model Abstraction Layer

**Files:**
- Create: `src/report_check/models/base.py`
- Create: `src/report_check/models/manager.py`
- Create: `src/report_check/models/openai_adapter.py`
- Create: `src/report_check/models/qwen_adapter.py`
- Test: `tests/test_models/test_manager.py`

- [ ] **Step 1: Write failing test for ModelManager**

`tests/test_models/test_manager.py`:
```python
import pytest
from unittest.mock import AsyncMock, patch

from report_check.models.base import BaseModelAdapter, ModelType
from report_check.models.manager import ModelManager


class FakeAdapter(BaseModelAdapter):
    async def call_text_model(self, prompt: str, **kwargs) -> str:
        return "fake text response"

    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        return "fake multimodal response"

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True


class TestModelManager:
    def test_register_and_get_adapter(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))

        adapter = manager.get_adapter("fake")
        assert isinstance(adapter, FakeAdapter)

    def test_get_default_adapter(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))

        adapter = manager.get_adapter()
        assert isinstance(adapter, FakeAdapter)

    def test_get_unknown_adapter_raises(self):
        manager = ModelManager(default_provider="fake")
        with pytest.raises(ValueError, match="Unknown provider"):
            manager.get_adapter("nonexistent")

    @pytest.mark.asyncio
    async def test_call_text_model(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))

        result = await manager.call_text_model("hello")
        assert result == "fake text response"

    @pytest.mark.asyncio
    async def test_call_multimodal_model(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))

        result = await manager.call_multimodal_model("hello", b"image_data")
        assert result == "fake multimodal response"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        adapter = FakeAdapter({})
        call_count = 0

        async def failing_then_success(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"

        adapter.call_text_model = failing_then_success

        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", adapter)

        result = await manager.call_text_model("test", retry=3)
        assert result == "success"
        assert call_count == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_models/test_manager.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement BaseModelAdapter**

`src/report_check/models/base.py`:
```python
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class ModelType(Enum):
    TEXT = "text"
    MULTIMODAL = "multimodal"


class BaseModelAdapter(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    async def call_text_model(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        pass

    @abstractmethod
    def supports_model_type(self, model_type: ModelType) -> bool:
        pass
```

- [ ] **Step 4: Implement ModelManager**

`src/report_check/models/manager.py`:
```python
import asyncio
import logging
from typing import Any

from report_check.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages model adapters with retry support."""

    def __init__(self, default_provider: str = "openai"):
        self.default_provider = default_provider
        self._adapters: dict[str, BaseModelAdapter] = {}

    def register_adapter(self, name: str, adapter: BaseModelAdapter):
        self._adapters[name] = adapter

    def get_adapter(self, provider: str | None = None) -> BaseModelAdapter:
        provider = provider or self.default_provider
        if provider not in self._adapters:
            raise ValueError(f"Unknown provider: {provider}")
        return self._adapters[provider]

    async def call_text_model(
        self,
        prompt: str,
        provider: str | None = None,
        retry: int = 3,
        **kwargs,
    ) -> str:
        adapter = self.get_adapter(provider)
        return await self._with_retry(
            adapter.call_text_model, retry, prompt, **kwargs
        )

    async def call_multimodal_model(
        self,
        prompt: str,
        image: bytes,
        provider: str | None = None,
        retry: int = 3,
        **kwargs,
    ) -> str:
        adapter = self.get_adapter(provider)
        return await self._with_retry(
            adapter.call_multimodal_model, retry, prompt, image=image, **kwargs
        )

    async def _with_retry(self, func, max_retries: int, *args, **kwargs):
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(
                    f"Call failed (attempt {attempt + 1}/{max_retries}): {e}"
                )
                await asyncio.sleep(min(2**attempt, 10))
```

- [ ] **Step 5: Implement OpenAIAdapter and QwenAdapter**

`src/report_check/models/openai_adapter.py`:
```python
import base64
from typing import Any

from openai import AsyncOpenAI

from report_check.models.base import BaseModelAdapter, ModelType


class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.client = AsyncOpenAI(
            api_key=config.get("api_key", ""),
            base_url=config.get("base_url"),
        )
        self.text_model = config.get("text_model", "gpt-4o")
        self.multimodal_model = config.get("multimodal_model", "gpt-4o")

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=self.text_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 2000),
        )
        return response.choices[0].message.content

    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        response = await self.client.chat.completions.create(
            model=self.multimodal_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                    ],
                }
            ],
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 1000),
        )
        return response.choices[0].message.content

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True
```

`src/report_check/models/qwen_adapter.py`:
```python
import base64
from typing import Any

import httpx

from report_check.models.base import BaseModelAdapter, ModelType


class QwenAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.text_model = config.get("text_model", "qwen-turbo")
        self.multimodal_model = config.get("multimodal_model", "qwen-vl-plus")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.text_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": kwargs.get("temperature", 0.1),
                    "max_tokens": kwargs.get("max_tokens", 2000),
                },
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": self.multimodal_model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
                            ],
                        }
                    ],
                    "temperature": kwargs.get("temperature", 0.1),
                    "max_tokens": kwargs.get("max_tokens", 1000),
                },
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_models/test_manager.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/report_check/models/ tests/test_models/
git commit -m "feat: AI model abstraction with OpenAI and Qwen adapters"
```

---

### Task 6: Rule Engine (Validator + Variable Resolver + Engine)

**Files:**
- Create: `src/report_check/engine/validator.py`
- Create: `src/report_check/engine/variable_resolver.py`
- Create: `src/report_check/engine/rule_engine.py`
- Test: `tests/test_engine/test_validator.py`
- Test: `tests/test_engine/test_variable_resolver.py`
- Test: `tests/test_engine/test_rule_engine.py`

- [ ] **Step 1: Write failing test for RuleValidator**

`tests/test_engine/test_validator.py`:
```python
import pytest

from report_check.engine.validator import RuleValidator, ValidationResult


class TestRuleValidator:
    def test_valid_text_rule(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {
                    "id": "r1",
                    "name": "test",
                    "type": "text",
                    "enabled": True,
                    "config": {
                        "keywords": ["交付内容"],
                        "match_mode": "any",
                    },
                }
            ]
        }
        result = validator.validate(dsl)
        assert result.is_valid

    def test_missing_rules_key(self):
        validator = RuleValidator()
        result = validator.validate({})
        assert not result.is_valid
        assert any("rules" in e["message"] for e in result.errors)

    def test_missing_required_fields(self):
        validator = RuleValidator()
        dsl = {"rules": [{"id": "r1"}]}
        result = validator.validate(dsl)
        assert not result.is_valid

    def test_unknown_rule_type(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {"id": "r1", "name": "t", "type": "unknown", "config": {}}
            ]
        }
        result = validator.validate(dsl)
        assert not result.is_valid

    def test_text_rule_missing_keywords(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {"id": "r1", "name": "t", "type": "text", "config": {}}
            ]
        }
        result = validator.validate(dsl)
        assert not result.is_valid

    def test_valid_semantic_rule(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {
                    "id": "r1",
                    "name": "t",
                    "type": "semantic",
                    "config": {"requirement": "must contain X"},
                }
            ]
        }
        result = validator.validate(dsl)
        assert result.is_valid

    def test_valid_image_rule(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {
                    "id": "r1",
                    "name": "t",
                    "type": "image",
                    "config": {"requirement": "clean room"},
                }
            ]
        }
        result = validator.validate(dsl)
        assert result.is_valid

    def test_valid_api_rule(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {
                    "id": "r1",
                    "name": "t",
                    "type": "api",
                    "config": {
                        "extract": {"type": "image", "description": "signature"},
                        "api": {
                            "name": "sig",
                            "endpoint": "https://api.example.com/check",
                            "method": "POST",
                        },
                        "validation": {
                            "success_field": "status",
                            "success_value": "ok",
                            "operator": "eq",
                        },
                    },
                }
            ]
        }
        result = validator.validate(dsl)
        assert result.is_valid

    def test_valid_external_data_rule(self):
        validator = RuleValidator()
        dsl = {
            "rules": [
                {
                    "id": "r1",
                    "name": "t",
                    "type": "external_data",
                    "config": {
                        "extract": {"type": "text", "description": "device list"},
                        "external_api": {
                            "name": "inventory",
                            "endpoint": "https://api.example.com/devices",
                            "method": "GET",
                        },
                        "analysis": {
                            "requirement": "devices must match",
                        },
                    },
                }
            ]
        }
        result = validator.validate(dsl)
        assert result.is_valid
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_engine/test_validator.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement RuleValidator**

`src/report_check/engine/validator.py`:
```python
from dataclasses import dataclass, field

VALID_TYPES = {"text", "semantic", "image", "api", "external_data"}
VALID_OPERATORS = {"eq", "neq", "contains", "gt", "gte"}


@dataclass
class ValidationResult:
    is_valid: bool = True
    errors: list[dict] = field(default_factory=list)

    def add_error(self, rule_id: str, field_name: str, message: str):
        self.is_valid = False
        self.errors.append({
            "rule_id": rule_id,
            "field": field_name,
            "message": message,
        })


class RuleValidator:
    """Validate rule DSL structure and content."""

    def validate(self, dsl: dict) -> ValidationResult:
        result = ValidationResult()

        if "rules" not in dsl:
            result.add_error("", "rules", "缺少 rules 字段")
            return result

        if not isinstance(dsl["rules"], list):
            result.add_error("", "rules", "rules 必须是数组")
            return result

        for rule in dsl["rules"]:
            self._validate_rule(rule, result)

        return result

    def _validate_rule(self, rule: dict, result: ValidationResult):
        rule_id = rule.get("id", "unknown")

        # Required fields
        for field_name in ("id", "name", "type", "config"):
            if field_name not in rule:
                result.add_error(rule_id, field_name, f"缺少 {field_name} 字段")

        if "type" not in rule:
            return

        rule_type = rule["type"]
        if rule_type not in VALID_TYPES:
            result.add_error(rule_id, "type", f"未知的规则类型: {rule_type}")
            return

        if "config" not in rule:
            return

        config = rule["config"]
        validator = {
            "text": self._validate_text_config,
            "semantic": self._validate_semantic_config,
            "image": self._validate_image_config,
            "api": self._validate_api_config,
            "external_data": self._validate_external_data_config,
        }.get(rule_type)

        if validator:
            validator(rule_id, config, result)

    def _validate_text_config(self, rule_id: str, config: dict, result: ValidationResult):
        if "keywords" not in config or not config["keywords"]:
            result.add_error(rule_id, "config.keywords", "keywords 不能为空")

    def _validate_semantic_config(self, rule_id: str, config: dict, result: ValidationResult):
        if "requirement" not in config or not config["requirement"]:
            result.add_error(rule_id, "config.requirement", "requirement 不能为空")

    def _validate_image_config(self, rule_id: str, config: dict, result: ValidationResult):
        if "requirement" not in config or not config["requirement"]:
            result.add_error(rule_id, "config.requirement", "requirement 不能为空")

    def _validate_api_config(self, rule_id: str, config: dict, result: ValidationResult):
        for section in ("extract", "api", "validation"):
            if section not in config:
                result.add_error(rule_id, f"config.{section}", f"缺少 {section} 字段")

        if "extract" in config:
            extract = config["extract"]
            if "type" not in extract:
                result.add_error(rule_id, "config.extract.type", "缺少 type 字段")
            if "description" not in extract:
                result.add_error(rule_id, "config.extract.description", "缺少 description 字段")

        if "api" in config:
            api = config["api"]
            for f in ("name", "endpoint", "method"):
                if f not in api:
                    result.add_error(rule_id, f"config.api.{f}", f"缺少 {f} 字段")

        if "validation" in config:
            v = config["validation"]
            for f in ("success_field", "success_value", "operator"):
                if f not in v:
                    result.add_error(rule_id, f"config.validation.{f}", f"缺少 {f} 字段")
            if v.get("operator") and v["operator"] not in VALID_OPERATORS:
                result.add_error(
                    rule_id,
                    "config.validation.operator",
                    f"不支持的操作符: {v['operator']}",
                )

    def _validate_external_data_config(self, rule_id: str, config: dict, result: ValidationResult):
        for section in ("extract", "external_api", "analysis"):
            if section not in config:
                result.add_error(rule_id, f"config.{section}", f"缺少 {section} 字段")

        if "extract" in config:
            if "description" not in config["extract"]:
                result.add_error(rule_id, "config.extract.description", "缺少 description 字段")

        if "external_api" in config:
            api = config["external_api"]
            for f in ("name", "endpoint", "method"):
                if f not in api:
                    result.add_error(rule_id, f"config.external_api.{f}", f"缺少 {f} 字段")

        if "analysis" in config:
            if "requirement" not in config["analysis"]:
                result.add_error(rule_id, "config.analysis.requirement", "缺少 requirement 字段")
```

- [ ] **Step 4: Write failing test for VariableResolver**

`tests/test_engine/test_variable_resolver.py`:
```python
import pytest

from report_check.engine.variable_resolver import VariableResolver
from report_check.core.exceptions import VariableMissingError


class TestVariableResolver:
    def test_resolve_context_var(self):
        resolver = VariableResolver(
            context_vars={"project_id": "proj-123"},
        )
        result = resolver.resolve("https://api.com?id=${project_id}")
        assert result == "https://api.com?id=proj-123"

    def test_resolve_env_var(self, monkeypatch):
        monkeypatch.setenv("API_TOKEN", "secret")
        resolver = VariableResolver()
        result = resolver.resolve("Bearer ${API_TOKEN}")
        assert result == "Bearer secret"

    def test_resolve_builtin_var(self):
        resolver = VariableResolver(
            builtins={"task_id": "task-001"},
        )
        result = resolver.resolve("task: ${task_id}")
        assert result == "task: task-001"

    def test_missing_var_raises(self):
        resolver = VariableResolver()
        with pytest.raises(VariableMissingError, match="unknown_var"):
            resolver.resolve("${unknown_var}")

    def test_no_vars_passthrough(self):
        resolver = VariableResolver()
        result = resolver.resolve("no variables here")
        assert result == "no variables here"

    def test_resolve_dict_recursively(self):
        resolver = VariableResolver(
            context_vars={"id": "123"},
        )
        data = {"url": "https://api.com/${id}", "nested": {"key": "${id}"}}
        result = resolver.resolve_dict(data)
        assert result["url"] == "https://api.com/123"
        assert result["nested"]["key"] == "123"
```

- [ ] **Step 5: Run variable resolver tests to verify they fail**

```bash
uv run pytest tests/test_engine/test_variable_resolver.py -v
```

Expected: FAIL

- [ ] **Step 6: Implement VariableResolver**

`src/report_check/engine/variable_resolver.py`:
```python
import os
import re
from typing import Any

from report_check.core.exceptions import VariableMissingError

VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


class VariableResolver:
    """Resolve ${variable} references in rule configs."""

    def __init__(
        self,
        context_vars: dict[str, str] | None = None,
        builtins: dict[str, str] | None = None,
    ):
        self.context_vars = context_vars or {}
        self.builtins = builtins or {}

    def resolve(self, value: str) -> str:
        """Resolve all ${var} in a string."""
        def _replace(match: re.Match) -> str:
            var_name = match.group(1)
            # Check context vars first
            if var_name in self.context_vars:
                return str(self.context_vars[var_name])
            # Then builtins
            if var_name in self.builtins:
                return str(self.builtins[var_name])
            # Then env vars
            env_val = os.environ.get(var_name)
            if env_val is not None:
                return env_val
            raise VariableMissingError(f"变量未定义: {var_name}")

        return VAR_PATTERN.sub(_replace, value)

    def resolve_dict(self, data: Any) -> Any:
        """Recursively resolve variables in a dict/list/str."""
        if isinstance(data, str):
            return self.resolve(data)
        elif isinstance(data, dict):
            return {k: self.resolve_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.resolve_dict(item) for item in data]
        return data
```

- [ ] **Step 7: Write failing test for RuleEngine**

`tests/test_engine/test_rule_engine.py`:
```python
from report_check.engine.rule_engine import RuleEngine


class TestRuleEngine:
    def test_get_rules_filters_disabled(self):
        dsl = {
            "rules": [
                {"id": "r1", "name": "a", "type": "text", "enabled": True, "config": {"keywords": ["x"]}},
                {"id": "r2", "name": "b", "type": "text", "enabled": False, "config": {"keywords": ["y"]}},
            ]
        }
        engine = RuleEngine(dsl)
        rules = engine.get_rules()
        assert len(rules) == 1
        assert rules[0]["id"] == "r1"

    def test_get_rules_default_enabled(self):
        dsl = {
            "rules": [
                {"id": "r1", "name": "a", "type": "text", "config": {"keywords": ["x"]}},
            ]
        }
        engine = RuleEngine(dsl)
        rules = engine.get_rules()
        assert len(rules) == 1

    def test_merge_with_base_template(self):
        base_rules = [
            {"id": "base1", "name": "base", "type": "text", "config": {"keywords": ["a"]}},
            {"id": "base2", "name": "base2", "type": "text", "config": {"keywords": ["b"]}},
        ]
        dsl = {
            "rules": [
                {"id": "base1", "name": "override", "type": "text", "config": {"keywords": ["c"]}},
                {"id": "custom1", "name": "custom", "type": "text", "config": {"keywords": ["d"]}},
            ]
        }
        engine = RuleEngine(dsl, base_rules=base_rules)
        rules = engine.get_rules()
        assert len(rules) == 3
        # base1 should be overridden
        r1 = next(r for r in rules if r["id"] == "base1")
        assert r1["name"] == "override"

    def test_disable_base_rule_via_override(self):
        base_rules = [
            {"id": "base1", "name": "base", "type": "text", "config": {"keywords": ["a"]}},
        ]
        dsl = {
            "rules": [
                {"id": "base1", "name": "base", "type": "text", "enabled": False, "config": {"keywords": ["a"]}},
            ]
        }
        engine = RuleEngine(dsl, base_rules=base_rules)
        rules = engine.get_rules()
        assert len(rules) == 0
```

- [ ] **Step 8: Run rule engine tests to verify they fail**

```bash
uv run pytest tests/test_engine/test_rule_engine.py -v
```

Expected: FAIL

- [ ] **Step 9: Implement RuleEngine**

`src/report_check/engine/rule_engine.py`:
```python
class RuleEngine:
    """Parse and manage rule DSL, handle template inheritance."""

    def __init__(self, dsl: dict, base_rules: list[dict] | None = None):
        self.dsl = dsl
        self.base_rules = base_rules or []
        self._merged_rules: list[dict] | None = None

    def get_rules(self) -> list[dict]:
        """Get all enabled rules after merging with base template."""
        if self._merged_rules is None:
            self._merged_rules = self._merge_rules()
        return [r for r in self._merged_rules if r.get("enabled", True)]

    def _merge_rules(self) -> list[dict]:
        """Merge base rules with user-defined rules."""
        user_rules = self.dsl.get("rules", [])

        if not self.base_rules:
            return list(user_rules)

        # Index user rules by id for quick lookup
        user_by_id = {r["id"]: r for r in user_rules}
        user_ids_seen = set()

        merged = []
        # Process base rules: override if user has same id
        for base_rule in self.base_rules:
            if base_rule["id"] in user_by_id:
                merged.append(user_by_id[base_rule["id"]])
                user_ids_seen.add(base_rule["id"])
            else:
                merged.append(base_rule)

        # Append remaining user rules (new ones)
        for user_rule in user_rules:
            if user_rule["id"] not in user_ids_seen:
                merged.append(user_rule)

        return merged
```

- [ ] **Step 10: Run all engine tests**

```bash
uv run pytest tests/test_engine/ -v
```

Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add src/report_check/engine/ tests/test_engine/
git commit -m "feat: rule engine with validator, variable resolver, and template merge"
```

---

### Task 7: Checker Base Class and TextChecker

**Files:**
- Create: `src/report_check/checkers/base.py`
- Create: `src/report_check/checkers/factory.py`
- Create: `src/report_check/checkers/text.py`
- Test: `tests/test_checkers/test_text.py`

- [ ] **Step 1: Write failing test for TextChecker**

`tests/test_checkers/test_text.py`:
```python
import pytest

from report_check.checkers.text import TextChecker
from report_check.checkers.base import CheckResult
from report_check.parser.excel import ExcelParser


class TestTextChecker:
    @pytest.mark.asyncio
    async def test_keyword_found(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        checker = TextChecker(report, model_manager=None)

        result = await checker.check({
            "keywords": ["交付内容"],
            "match_mode": "any",
        })
        assert isinstance(result, CheckResult)
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_keyword_not_found(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        checker = TextChecker(report, model_manager=None)

        result = await checker.check({
            "keywords": ["不存在的内容"],
            "match_mode": "any",
        })
        assert result.status == "failed"
        assert len(result.suggestion) > 0

    @pytest.mark.asyncio
    async def test_match_mode_all(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        checker = TextChecker(report, model_manager=None)

        result = await checker.check({
            "keywords": ["交付内容", "移交记录"],
            "match_mode": "all",
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_match_mode_all_partial(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        checker = TextChecker(report, model_manager=None)

        result = await checker.check({
            "keywords": ["交付内容", "不存在的关键词"],
            "match_mode": "all",
        })
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_min_occurrences(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))
        checker = TextChecker(report, model_manager=None)

        result = await checker.check({
            "keywords": ["交付内容"],
            "match_mode": "any",
            "min_occurrences": 100,
        })
        assert result.status == "failed"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_checkers/test_text.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement CheckResult and BaseChecker**

`src/report_check/checkers/base.py`:
```python
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from report_check.models.manager import ModelManager
from report_check.parser.models import ReportData
from report_check.parser.summarizer import ReportSummarizer

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    rule_id: str = ""
    rule_name: str = ""
    rule_type: str = ""
    status: str = "error"  # passed, failed, error
    location: dict = field(default_factory=dict)
    message: str = ""
    suggestion: str = ""
    example: str = ""
    confidence: float = 1.0
    execution_time: float = 0.0


class BaseChecker(ABC):
    def __init__(self, report_data: ReportData, model_manager: ModelManager | None):
        self.report_data = report_data
        self.model_manager = model_manager

    @abstractmethod
    async def check(self, rule_config: dict) -> CheckResult:
        pass

    async def locate_content(
        self, description: str, context_hint: str = ""
    ) -> list[dict] | None:
        """Use AI to locate content in the report.

        Returns:
            list[dict]: locations found
            []: AI returned found=false (content not in report)
            None: AI response was unparseable
        """
        if self.model_manager is None:
            return None

        summarizer = ReportSummarizer()
        summary = summarizer.summarize(self.report_data)

        prompt = f"""请在以下 Excel 报告中定位符合描述的内容。
描述：{description}
提示：{context_hint}

报告结构：
{summary}

请以 JSON 格式返回结果：
{{
  "found": true/false,
  "locations": [
    {{
      "cell_range": "B3:D5",
      "context": "在移交记录章节中",
      "confidence": 0.9
    }}
  ],
  "reason": "定位理由"
}}"""

        response = await self.model_manager.call_text_model(prompt)
        locations = self._parse_location_response(response)

        if locations is None:
            # Retry once
            response = await self.model_manager.call_text_model(prompt)
            locations = self._parse_location_response(response)

        return locations

    def _parse_location_response(self, response: str) -> list[dict] | None:
        """Parse AI response for locations. Returns None on parse failure."""
        try:
            # Try to extract JSON from response
            text = response.strip()
            # Handle markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            data = json.loads(text)

            if not data.get("found", False):
                return []

            return data.get("locations", [])
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.warning(f"Failed to parse location response: {e}")
            return None
```

- [ ] **Step 4: Implement TextChecker**

`src/report_check/checkers/text.py`:
```python
from report_check.checkers.base import BaseChecker, CheckResult


class TextChecker(BaseChecker):
    """Check for fixed text keywords in the report."""

    async def check(self, rule_config: dict) -> CheckResult:
        keywords = rule_config.get("keywords", [])
        match_mode = rule_config.get("match_mode", "any")
        case_sensitive = rule_config.get("case_sensitive", False)
        min_occurrences = rule_config.get("min_occurrences", 1)

        found_keywords: dict[str, list] = {}

        for keyword in keywords:
            matches = self.report_data.search_text(keyword, case_sensitive)
            if matches:
                found_keywords[keyword] = matches

        if match_mode == "all":
            all_found = len(found_keywords) == len(keywords)
            if all_found:
                first_match = list(found_keywords.values())[0][0]
                return CheckResult(
                    status="passed",
                    location={
                        "type": "cell_range",
                        "value": first_match.cell_ref,
                        "context": f"找到所有关键词",
                    },
                    message=f"找到所有关键词: {', '.join(keywords)}",
                )
            else:
                missing = [k for k in keywords if k not in found_keywords]
                return CheckResult(
                    status="failed",
                    location={"type": "not_found"},
                    message=f"未找到关键词: {', '.join(missing)}",
                    suggestion=f"请在报告中添加: {', '.join(missing)}",
                )

        elif match_mode == "any":
            total_matches = sum(len(m) for m in found_keywords.values())
            if found_keywords and total_matches >= min_occurrences:
                first_match = list(found_keywords.values())[0][0]
                return CheckResult(
                    status="passed",
                    location={
                        "type": "cell_range",
                        "value": first_match.cell_ref,
                        "context": f"找到关键词: {list(found_keywords.keys())[0]}",
                    },
                    message=f"找到关键词 (共 {total_matches} 处)",
                )
            elif found_keywords and total_matches < min_occurrences:
                return CheckResult(
                    status="failed",
                    location={"type": "not_found"},
                    message=f"关键词出现次数不足 (需要 {min_occurrences}，找到 {total_matches})",
                    suggestion=f"请确保关键词至少出现 {min_occurrences} 次",
                )
            else:
                return CheckResult(
                    status="failed",
                    location={"type": "not_found"},
                    message=f"未找到关键词: {', '.join(keywords)}",
                    suggestion=f"请在报告中添加: {keywords[0]}",
                )

        elif match_mode == "exact":
            for keyword in keywords:
                for cell in self.report_data.cells:
                    value = str(cell.value)
                    if (not case_sensitive and value.lower() == keyword.lower()) or \
                       (case_sensitive and value == keyword):
                        return CheckResult(
                            status="passed",
                            location={
                                "type": "cell_range",
                                "value": cell.cell_ref,
                                "context": f"精确匹配: {keyword}",
                            },
                            message=f"精确匹配到: {keyword}",
                        )
            return CheckResult(
                status="failed",
                location={"type": "not_found"},
                message=f"未精确匹配到: {', '.join(keywords)}",
                suggestion=f"请在报告中添加: {keywords[0]}",
            )

        return CheckResult(
            status="error",
            message=f"不支持的匹配模式: {match_mode}",
        )
```

- [ ] **Step 5: Implement CheckerFactory**

`src/report_check/checkers/factory.py`:
```python
from report_check.checkers.base import BaseChecker
from report_check.checkers.text import TextChecker
from report_check.models.manager import ModelManager
from report_check.parser.models import ReportData


class CheckerFactory:
    CHECKER_MAP: dict[str, type[BaseChecker]] = {
        "text": TextChecker,
    }

    def __init__(self, report_data: ReportData, model_manager: ModelManager | None):
        self.report_data = report_data
        self.model_manager = model_manager

    def create(self, checker_type: str) -> BaseChecker:
        checker_class = self.CHECKER_MAP.get(checker_type)
        if not checker_class:
            raise ValueError(f"Unknown checker type: {checker_type}")
        return checker_class(self.report_data, self.model_manager)

    @classmethod
    def register(cls, name: str, checker_class: type[BaseChecker]):
        cls.CHECKER_MAP[name] = checker_class
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_checkers/test_text.py -v
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add src/report_check/checkers/ tests/test_checkers/
git commit -m "feat: checker base class, TextChecker, and CheckerFactory"
```

---

### Task 8: SemanticChecker and ImageChecker

**Files:**
- Create: `src/report_check/checkers/semantic.py`
- Create: `src/report_check/checkers/image.py`
- Test: `tests/test_checkers/test_semantic.py`
- Test: `tests/test_checkers/test_image.py`

- [ ] **Step 1: Write tests for SemanticChecker (with mocked AI)**

`tests/test_checkers/test_semantic.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock

from report_check.checkers.semantic import SemanticChecker
from report_check.parser.excel import ExcelParser


def make_mock_model_manager(locate_response: str, check_response: str):
    mm = AsyncMock()
    mm.call_text_model = AsyncMock(side_effect=[locate_response, check_response])
    return mm


class TestSemanticChecker:
    @pytest.mark.asyncio
    async def test_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A10:B13", "context": "移交记录", "confidence": 0.9}],
            "reason": "found handover section",
        })
        check_resp = json.dumps({
            "passed": True,
            "message": "包含移交人、移交时间、移交命令",
            "confidence": 0.95,
        })
        mm = make_mock_model_manager(locate_resp, check_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "移交记录中要包含移交人、移交时间、移交命令",
            "context_hint": "移交相关章节",
            "model": "text",
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_failed_content_not_found(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": False,
            "locations": [],
            "reason": "not found",
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "需要包含不存在的内容",
        })
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_failed_check(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A10:B13", "context": "移交", "confidence": 0.9}],
            "reason": "found",
        })
        check_resp = json.dumps({
            "passed": False,
            "message": "缺少移交命令",
            "suggestion": "请添加移交命令字段",
            "confidence": 0.8,
        })
        mm = make_mock_model_manager(locate_resp, check_resp)
        checker = SemanticChecker(report, mm)

        result = await checker.check({
            "requirement": "需要包含移交命令",
        })
        assert result.status == "failed"
```

- [ ] **Step 2: Write tests for ImageChecker (with mocked AI)**

`tests/test_checkers/test_image.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock

from report_check.checkers.image import ImageChecker
from report_check.parser.excel import ExcelParser
from report_check.storage.cache import ResultCache


class TestImageChecker:
    @pytest.mark.asyncio
    async def test_image_matched(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        check_resp = json.dumps({
            "matched": True,
            "confidence": 0.85,
            "reason": "图片符合要求",
        })
        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=check_resp)
        checker = ImageChecker(report, mm)

        result = await checker.check({
            "requirement": "clean room",
            "min_match_count": 1,
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_no_images(self, sample_excel_no_images):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_no_images))

        checker = ImageChecker(report, model_manager=None)

        result = await checker.check({
            "requirement": "clean room",
            "min_match_count": 1,
        })
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_image_filter_by_nearby_text(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        check_resp = json.dumps({
            "matched": True,
            "confidence": 0.9,
            "reason": "matches",
        })
        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=check_resp)
        checker = ImageChecker(report, mm)

        result = await checker.check({
            "requirement": "test image",
            "image_filter": {
                "use_nearby_text": True,
                "keywords": ["移交"],  # Should match nearby cells
            },
            "min_match_count": 1,
        })
        assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_cache_hit(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        mm = AsyncMock()
        mm.call_multimodal_model = AsyncMock(return_value=json.dumps({
            "matched": True, "confidence": 0.9, "reason": "ok",
        }))
        checker = ImageChecker(report, mm)
        cache = ResultCache()
        checker.cache = cache

        # First call
        await checker.check({"requirement": "test", "min_match_count": 1})
        first_call_count = mm.call_multimodal_model.call_count

        # Second call should use cache
        await checker.check({"requirement": "test", "min_match_count": 1})
        assert mm.call_multimodal_model.call_count == first_call_count
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_checkers/test_semantic.py tests/test_checkers/test_image.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement SemanticChecker**

`src/report_check/checkers/semantic.py`:
```python
import json
import logging
import time

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.parser.summarizer import ReportSummarizer

logger = logging.getLogger(__name__)


class SemanticChecker(BaseChecker):
    """Use AI to check semantic content in the report."""

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        requirement = rule_config.get("requirement", "")
        context_hint = rule_config.get("context_hint", "")

        # Step 1: Locate content
        locations = await self.locate_content(requirement, context_hint)

        if locations is None:
            return CheckResult(
                status="error",
                message="AI 定位内容失败（响应格式异常）",
                execution_time=time.time() - start,
            )

        if not locations:
            return CheckResult(
                status="failed",
                location={"type": "not_found"},
                message=f"未找到符合要求的内容: {requirement}",
                suggestion=f"请在报告中添加相关内容",
                execution_time=time.time() - start,
            )

        # Step 2: Verify content at located region
        summarizer = ReportSummarizer()
        for loc in locations:
            cell_range = loc.get("cell_range", "")
            # Parse cell range to get rows
            region_text = self._get_region_text(summarizer, cell_range)

            check_result = await self._semantic_check(region_text, requirement)

            if check_result.get("passed", False):
                return CheckResult(
                    status="passed",
                    location={
                        "type": "cell_range",
                        "value": cell_range,
                        "context": loc.get("context", ""),
                    },
                    message=check_result.get("message", "检查通过"),
                    confidence=check_result.get("confidence", 0.9),
                    execution_time=time.time() - start,
                )

        # All locations checked, none passed
        return CheckResult(
            status="failed",
            location={
                "type": "cell_range",
                "value": locations[0].get("cell_range", ""),
                "context": locations[0].get("context", ""),
            },
            message=check_result.get("message", "内容不满足要求"),
            suggestion=check_result.get("suggestion", f"请确保报告中包含: {requirement}"),
            execution_time=time.time() - start,
        )

    def _get_region_text(self, summarizer: ReportSummarizer, cell_range: str) -> str:
        """Extract text from a cell range string like 'A10:B13'."""
        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            return summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            # If range parsing fails, use full summary
            return summarizer.summarize(self.report_data)

    async def _semantic_check(self, content: str, requirement: str) -> dict:
        """Use AI to verify content meets requirement."""
        prompt = f"""请检查以下内容是否满足要求。

要求：{requirement}

内容：
{content}

请以 JSON 格式返回：
{{
  "passed": true/false,
  "message": "检查结论",
  "suggestion": "如果不满足，给出修改建议",
  "confidence": 0.0-1.0
}}"""

        response = await self.model_manager.call_text_model(prompt)
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Failed to parse semantic check response")
            return {"passed": False, "message": "AI 响应格式异常"}
```

- [ ] **Step 5: Implement ImageChecker**

`src/report_check/checkers/image.py`:
```python
import json
import logging
import time

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.storage.cache import ResultCache

logger = logging.getLogger(__name__)


class ImageChecker(BaseChecker):
    """Check images in the report using multimodal AI."""

    def __init__(self, report_data, model_manager):
        super().__init__(report_data, model_manager)
        self.cache = ResultCache()

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        requirement = rule_config.get("requirement", "")
        min_match = rule_config.get("min_match_count", 1)
        image_filter = rule_config.get("image_filter", {})

        images = self._get_images(image_filter)

        if not images:
            return CheckResult(
                status="failed",
                location={"type": "images", "count": 0},
                message="报告中未找到图片",
                suggestion="请在报告中添加相关图片",
                execution_time=time.time() - start,
            )

        matched = []
        for img in images:
            cache_key = self.cache.get_cache_key(img.data, requirement)
            cached = self.cache.get(cache_key)

            if cached is not None:
                result = cached
            else:
                result = await self._check_image(img, requirement)
                self.cache.set(cache_key, result)

            if result.get("matched", False):
                matched.append((img, result))

        if len(matched) >= min_match:
            img, res = matched[0]
            return CheckResult(
                status="passed",
                location={
                    "type": "image",
                    "value": img.anchor.get("cell_ref", ""),
                    "context": f"找到 {len(matched)} 张符合要求的图片",
                },
                message=f"找到 {len(matched)} 张符合要求的图片",
                confidence=res.get("confidence", 0.9),
                execution_time=time.time() - start,
            )
        else:
            return CheckResult(
                status="failed",
                location={"type": "images", "count": len(images)},
                message=f"未找到足够的符合要求的图片 (需要 {min_match}，找到 {len(matched)})",
                suggestion="请添加符合要求的图片",
                execution_time=time.time() - start,
            )

    def _get_images(self, image_filter: dict) -> list:
        """Filter images based on nearby text keywords."""
        all_images = self.report_data.images
        if not image_filter.get("use_nearby_text", False):
            return all_images

        keywords = image_filter.get("keywords", [])
        if not keywords:
            return all_images

        filtered = []
        for img in all_images:
            nearby_text = " ".join(str(c.value) for c in img.nearby_cells)
            if any(kw in nearby_text for kw in keywords):
                filtered.append(img)

        # Fallback to all if no filter matches
        return filtered if filtered else all_images

    async def _check_image(self, img, requirement: str) -> dict:
        """Use multimodal model to check a single image."""
        if self.model_manager is None:
            return {"matched": False, "confidence": 0, "reason": "no model"}

        prompt = f"""请判断这张图片是否符合以下要求：{requirement}

请以 JSON 格式返回：
{{
  "matched": true/false,
  "confidence": 0.0-1.0,
  "reason": "判断理由"
}}"""

        try:
            response = await self.model_manager.call_multimodal_model(
                prompt, img.data
            )
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except Exception as e:
            logger.warning(f"Image check failed: {e}")
            return {"matched": False, "confidence": 0, "reason": str(e)}
```

- [ ] **Step 6: Register checkers in factory**

Update `src/report_check/checkers/factory.py`:
```python
from report_check.checkers.base import BaseChecker
from report_check.checkers.text import TextChecker
from report_check.checkers.semantic import SemanticChecker
from report_check.checkers.image import ImageChecker
from report_check.models.manager import ModelManager
from report_check.parser.models import ReportData


class CheckerFactory:
    CHECKER_MAP: dict[str, type[BaseChecker]] = {
        "text": TextChecker,
        "semantic": SemanticChecker,
        "image": ImageChecker,
    }

    def __init__(self, report_data: ReportData, model_manager: ModelManager | None):
        self.report_data = report_data
        self.model_manager = model_manager

    def create(self, checker_type: str) -> BaseChecker:
        checker_class = self.CHECKER_MAP.get(checker_type)
        if not checker_class:
            raise ValueError(f"Unknown checker type: {checker_type}")
        return checker_class(self.report_data, self.model_manager)

    @classmethod
    def register(cls, name: str, checker_class: type[BaseChecker]):
        cls.CHECKER_MAP[name] = checker_class
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_checkers/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/report_check/checkers/ tests/test_checkers/
git commit -m "feat: SemanticChecker and ImageChecker with AI integration"
```

---

### Task 9: ApiChecker and ExternalDataChecker

**Files:**
- Create: `src/report_check/checkers/api_check.py`
- Create: `src/report_check/checkers/external.py`
- Test: `tests/test_checkers/test_api_check.py`
- Test: `tests/test_checkers/test_external.py`

- [ ] **Step 1: Write tests for ApiChecker**

`tests/test_checkers/test_api_check.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch

from report_check.checkers.api_check import ApiChecker
from report_check.parser.excel import ExcelParser


class TestApiChecker:
    @pytest.mark.asyncio
    async def test_api_check_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        # Mock locate_content to find an image
        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A15", "context": "签名区域", "confidence": 0.9}],
            "reason": "found",
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)

        checker = ApiChecker(report, mm)

        # Mock the HTTP call
        with patch("report_check.checkers.api_check.httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = {"status": "valid"}
            mock_resp.raise_for_status = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_resp)
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "image",
                    "description": "签名图片",
                    "fallback": "last_image",
                },
                "api": {
                    "name": "sig_check",
                    "endpoint": "https://api.example.com/check",
                    "method": "POST",
                    "body": {"image": "${extracted_content}"},
                    "timeout": 10,
                },
                "validation": {
                    "success_field": "status",
                    "success_value": "valid",
                    "operator": "eq",
                    "error_message": "签名无效",
                },
            })
            assert result.status == "passed"

    @pytest.mark.asyncio
    async def test_api_check_content_not_found_uses_fallback(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({"found": False, "locations": [], "reason": "not found"})
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(return_value=locate_resp)

        checker = ApiChecker(report, mm)

        with patch("report_check.checkers.api_check.httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = {"status": "valid"}
            mock_resp.raise_for_status = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.post = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "image",
                    "description": "签名图片",
                    "fallback": "last_image",
                },
                "api": {
                    "name": "sig_check",
                    "endpoint": "https://api.example.com/check",
                    "method": "POST",
                },
                "validation": {
                    "success_field": "status",
                    "success_value": "valid",
                    "operator": "eq",
                },
            })
            # Should use fallback (last image) and still work
            assert result.status in ("passed", "error")

    @pytest.mark.asyncio
    async def test_validation_operators(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        checker = ApiChecker(report, AsyncMock())

        # eq
        assert checker._validate_response({"score": 100}, {"success_field": "score", "success_value": "100", "operator": "eq"})
        # neq
        assert checker._validate_response({"status": "ok"}, {"success_field": "status", "success_value": "error", "operator": "neq"})
        # contains
        assert checker._validate_response({"msg": "success!"}, {"success_field": "msg", "success_value": "success", "operator": "contains"})
        # gt
        assert checker._validate_response({"score": 90}, {"success_field": "score", "success_value": "80", "operator": "gt"})
        # gte
        assert checker._validate_response({"score": 80}, {"success_field": "score", "success_value": "80", "operator": "gte"})
```

- [ ] **Step 2: Write tests for ExternalDataChecker**

`tests/test_checkers/test_external.py`:
```python
import pytest
import json
from unittest.mock import AsyncMock, patch

from report_check.checkers.external import ExternalDataChecker
from report_check.parser.excel import ExcelParser


class TestExternalDataChecker:
    @pytest.mark.asyncio
    async def test_external_data_check_passed(self, sample_excel_path):
        parser = ExcelParser()
        report = parser.parse(str(sample_excel_path))

        locate_resp = json.dumps({
            "found": True,
            "locations": [{"cell_range": "A6:A7", "context": "设备列表", "confidence": 0.9}],
            "reason": "found",
        })
        analysis_resp = json.dumps({
            "passed": True,
            "message": "所有设备都在清单中",
            "confidence": 0.95,
        })
        mm = AsyncMock()
        mm.call_text_model = AsyncMock(side_effect=[locate_resp, analysis_resp])

        checker = ExternalDataChecker(report, mm)

        with patch("report_check.checkers.external.httpx.AsyncClient") as mock_client:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = {"data": {"devices": ["server1", "server2"]}}
            mock_resp.raise_for_status = AsyncMock()
            mock_client.return_value.__aenter__ = AsyncMock(return_value=mock_client.return_value)
            mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.return_value.get = AsyncMock(return_value=mock_resp)

            result = await checker.check({
                "extract": {
                    "type": "text",
                    "description": "设备列表",
                    "context_hint": "设备相关章节",
                },
                "external_api": {
                    "name": "inventory",
                    "endpoint": "https://api.example.com/devices",
                    "method": "GET",
                    "response_path": "data.devices",
                },
                "analysis": {
                    "requirement": "报告中的设备必须在清单中",
                },
            })
            assert result.status == "passed"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_checkers/test_api_check.py tests/test_checkers/test_external.py -v
```

Expected: FAIL

- [ ] **Step 4: Implement ApiChecker**

`src/report_check/checkers/api_check.py`:
```python
import base64
import json
import logging
import time
from typing import Any

import httpx

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.parser.models import ImageData

logger = logging.getLogger(__name__)


class ApiChecker(BaseChecker):
    """Extract content from report, call external API, validate response."""

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        extract_config = rule_config.get("extract", {})
        api_config = rule_config.get("api", {})
        validation_config = rule_config.get("validation", {})

        # Step 1: Extract content
        extracted = await self._extract_content(extract_config)
        if extracted is None:
            return CheckResult(
                status="error",
                location={"type": "not_found"},
                message="未找到要提取的内容",
                execution_time=time.time() - start,
            )

        # Step 2: Call API
        try:
            api_response = await self._call_api(api_config, extracted["content"])
        except Exception as e:
            return CheckResult(
                status="error",
                location=extracted.get("location", {}),
                message=f"API 调用失败: {str(e)}",
                execution_time=time.time() - start,
            )

        # Step 3: Validate
        is_valid = self._validate_response(api_response, validation_config)

        return CheckResult(
            status="passed" if is_valid else "failed",
            location=extracted.get("location", {}),
            message="验证通过" if is_valid else validation_config.get("error_message", "验证失败"),
            execution_time=time.time() - start,
        )

    async def _extract_content(self, extract_config: dict) -> dict | None:
        """Extract content from report using AI location or fallback."""
        extract_type = extract_config.get("type", "text")
        description = extract_config.get("description", "")
        context_hint = extract_config.get("context_hint", "")
        fallback = extract_config.get("fallback", "none")

        if extract_type == "image":
            return self._extract_image(description, context_hint, fallback)
        else:
            return await self._extract_text(description, context_hint)

    def _extract_image(
        self, description: str, context_hint: str, fallback: str
    ) -> dict | None:
        """Extract an image from the report."""
        images = self.report_data.images
        if not images:
            return None

        # For now, use fallback strategy directly
        # TODO: Use AI location when model_manager available
        if fallback == "last_image":
            img = images[-1]
        elif fallback == "first_image":
            img = images[0]
        else:
            if images:
                img = images[0]
            else:
                return None

        return {
            "content": base64.b64encode(img.data).decode("utf-8"),
            "location": {
                "type": "image",
                "value": img.anchor.get("cell_ref", ""),
            },
        }

    async def _extract_text(self, description: str, context_hint: str) -> dict | None:
        """Extract text from report using AI location."""
        locations = await self.locate_content(description, context_hint)

        if locations is None or not locations:
            return None

        from report_check.parser.summarizer import ReportSummarizer
        summarizer = ReportSummarizer()
        loc = locations[0]
        cell_range = loc.get("cell_range", "")

        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            text = summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            text = summarizer.summarize(self.report_data)

        return {
            "content": text,
            "location": {"type": "cell_range", "value": cell_range, "context": loc.get("context", "")},
        }

    async def _call_api(self, api_config: dict, content: Any) -> dict:
        """Call external API."""
        endpoint = api_config.get("endpoint", "")
        method = api_config.get("method", "GET").upper()
        headers = api_config.get("headers", {})
        timeout = api_config.get("timeout", 10)
        body = api_config.get("body", {})
        params = api_config.get("params", {})

        # Replace ${extracted_content} in body
        body_str = json.dumps(body)
        body_str = body_str.replace("${extracted_content}", str(content))
        body = json.loads(body_str)

        async with httpx.AsyncClient(timeout=timeout) as client:
            if method == "POST":
                resp = await client.post(endpoint, json=body, headers=headers)
            elif method == "GET":
                resp = await client.get(endpoint, params=params, headers=headers)
            else:
                resp = await client.request(method, endpoint, json=body, headers=headers)

            resp.raise_for_status()
            return resp.json()

    def _validate_response(self, response: dict, validation: dict) -> bool:
        """Validate API response using operator."""
        field = validation.get("success_field", "")
        expected = validation.get("success_value", "")
        operator = validation.get("operator", "eq")

        actual = str(response.get(field, ""))

        if operator == "eq":
            return actual == str(expected)
        elif operator == "neq":
            return actual != str(expected)
        elif operator == "contains":
            return str(expected) in actual
        elif operator == "gt":
            try:
                return float(actual) > float(expected)
            except ValueError:
                return False
        elif operator == "gte":
            try:
                return float(actual) >= float(expected)
            except ValueError:
                return False

        return False
```

- [ ] **Step 5: Implement ExternalDataChecker**

`src/report_check/checkers/external.py`:
```python
import json
import logging
import time
from typing import Any

import httpx

from report_check.checkers.base import BaseChecker, CheckResult
from report_check.parser.summarizer import ReportSummarizer

logger = logging.getLogger(__name__)


class ExternalDataChecker(BaseChecker):
    """Extract data from report, fetch external data, use AI to compare."""

    async def check(self, rule_config: dict) -> CheckResult:
        start = time.time()
        extract_config = rule_config.get("extract", {})
        api_config = rule_config.get("external_api", {})
        analysis_config = rule_config.get("analysis", {})

        # Step 1: Extract report data
        extracted = await self._extract_data(extract_config)
        if extracted is None:
            return CheckResult(
                status="failed",
                location={"type": "not_found"},
                message="未找到要提取的内容",
                execution_time=time.time() - start,
            )

        # Step 2: Fetch external data
        try:
            external_data = await self._fetch_external_data(api_config)
        except Exception as e:
            return CheckResult(
                status="error",
                location=extracted.get("location", {}),
                message=f"获取外部数据失败: {str(e)}",
                execution_time=time.time() - start,
            )

        # Step 3: AI analysis
        analysis_result = await self._analyze(
            extracted["content"], external_data, analysis_config
        )

        return CheckResult(
            status="passed" if analysis_result.get("passed") else "failed",
            location=extracted.get("location", {}),
            message=analysis_result.get("message", ""),
            suggestion=analysis_result.get("suggestion", ""),
            confidence=analysis_result.get("confidence", 0.9),
            execution_time=time.time() - start,
        )

    async def _extract_data(self, extract_config: dict) -> dict | None:
        """Use AI to locate and extract data from report."""
        description = extract_config.get("description", "")
        context_hint = extract_config.get("context_hint", "")

        locations = await self.locate_content(description, context_hint)
        if locations is None or not locations:
            return None

        summarizer = ReportSummarizer()
        loc = locations[0]
        cell_range = loc.get("cell_range", "")

        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            text = summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            text = summarizer.summarize(self.report_data)

        return {
            "content": text,
            "location": {"type": "cell_range", "value": cell_range, "context": loc.get("context", "")},
        }

    async def _fetch_external_data(self, api_config: dict) -> Any:
        """Fetch data from external API."""
        endpoint = api_config.get("endpoint", "")
        method = api_config.get("method", "GET").upper()
        headers = api_config.get("headers", {})
        params = api_config.get("params", {})
        response_path = api_config.get("response_path", "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            if method == "GET":
                resp = await client.get(endpoint, params=params, headers=headers)
            else:
                resp = await client.request(method, endpoint, headers=headers)

            resp.raise_for_status()
            data = resp.json()

        # Navigate response path (e.g., "data.devices")
        if response_path:
            for key in response_path.split("."):
                data = data[key]

        return data

    async def _analyze(
        self, report_data: str, external_data: Any, analysis_config: dict
    ) -> dict:
        """Use AI to compare report data with external data."""
        requirement = analysis_config.get("requirement", "")

        prompt = f"""请根据外部数据检查报告数据是否满足要求。

要求：{requirement}

报告数据：
{report_data}

外部数据：
{json.dumps(external_data, ensure_ascii=False, indent=2) if not isinstance(external_data, str) else external_data}

请以 JSON 格式返回：
{{
  "passed": true/false,
  "message": "分析结论",
  "suggestion": "如果不满足，给出修改建议",
  "confidence": 0.0-1.0
}}"""

        response = await self.model_manager.call_text_model(prompt)
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, IndexError):
            return {"passed": False, "message": "AI 响应格式异常"}
```

- [ ] **Step 6: Update CheckerFactory**

Update `src/report_check/checkers/factory.py` to add:
```python
from report_check.checkers.api_check import ApiChecker
from report_check.checkers.external import ExternalDataChecker

# Add to CHECKER_MAP:
    "api": ApiChecker,
    "external_data": ExternalDataChecker,
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
uv run pytest tests/test_checkers/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add src/report_check/checkers/ tests/test_checkers/
git commit -m "feat: ApiChecker and ExternalDataChecker"
```

---

### Task 10: Worker (TaskQueue + BackgroundWorker)

**Files:**
- Create: `src/report_check/worker/queue.py`
- Create: `src/report_check/worker/worker.py`

- [ ] **Step 1: Implement TaskQueue**

`src/report_check/worker/queue.py`:
```python
import asyncio


class TaskQueue:
    """In-memory async task queue."""

    def __init__(self):
        self._queue: asyncio.Queue[str] = asyncio.Queue()

    async def enqueue(self, task_id: str):
        await self._queue.put(task_id)

    async def dequeue(self) -> str:
        return await self._queue.get()

    def size(self) -> int:
        return self._queue.qsize()
```

- [ ] **Step 2: Implement BackgroundWorker**

`src/report_check/worker/worker.py`:
```python
import asyncio
import logging
import time

from report_check.checkers.factory import CheckerFactory
from report_check.engine.rule_engine import RuleEngine
from report_check.engine.variable_resolver import VariableResolver
from report_check.models.manager import ModelManager
from report_check.parser.excel import ExcelParser
from report_check.storage.database import Database, TaskStatus
from report_check.worker.queue import TaskQueue

logger = logging.getLogger(__name__)


class BackgroundWorker:
    """Process check tasks from the queue."""

    def __init__(
        self,
        db: Database,
        model_manager: ModelManager,
        task_queue: TaskQueue,
    ):
        self.db = db
        self.model_manager = model_manager
        self.task_queue = task_queue
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self):
        self._running = True

        # Recover orphaned tasks
        recovered = await self.db.recover_orphaned_tasks()
        for tid in recovered:
            await self.task_queue.enqueue(tid)
            logger.info(f"Re-enqueued recovered task: {tid}")

        self._task = asyncio.create_task(self._run_loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self):
        while self._running:
            try:
                task_id = await self.task_queue.dequeue()
                await self._process_task(task_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}", exc_info=True)

    async def _process_task(self, task_id: str):
        task = await self.db.get_task(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return

        try:
            await self.db.update_task_status(task_id, TaskStatus.PROCESSING)

            # Step 1: Parse Excel
            await self.db.update_task_progress(task_id, 10)
            parser = ExcelParser()
            report_data = parser.parse(task["file_path"])

            # Step 2: Load rules and resolve variables
            await self.db.update_task_progress(task_id, 20)
            engine = RuleEngine(task["rules"])
            rules = engine.get_rules()

            # Resolve variables in rule configs
            context_vars = task.get("context_vars", {}) or {}
            resolver = VariableResolver(
                context_vars=context_vars,
                builtins={"task_id": task_id},
            )
            for rule in rules:
                try:
                    rule["config"] = resolver.resolve_dict(rule["config"])
                except Exception as e:
                    logger.warning(f"Variable resolution failed for rule {rule['id']}: {e}")

            # Step 3: Execute checks
            factory = CheckerFactory(report_data, self.model_manager)
            results = []
            api_failure_counts: dict[str, int] = {}

            for i, rule in enumerate(rules):
                progress = 20 + int((i / max(len(rules), 1)) * 70)
                await self.db.update_task_progress(task_id, progress)

                start = time.time()

                # Check circuit breaker for API rules
                rule_type = rule["type"]
                if rule_type in ("api", "external_data"):
                    api_name = rule.get("config", {}).get("api", {}).get("name") or \
                               rule.get("config", {}).get("external_api", {}).get("name", "")
                    if api_failure_counts.get(api_name, 0) >= 3:
                        results.append({
                            "rule_id": rule["id"],
                            "rule_name": rule["name"],
                            "rule_type": rule_type,
                            "status": "error",
                            "location": {},
                            "message": f"API {api_name} 连续失败，已跳过",
                            "suggestion": "",
                            "example": "",
                            "confidence": 0,
                            "execution_time": 0,
                        })
                        continue

                checker = factory.create(rule_type)
                result = await checker.check(rule["config"])
                result.rule_id = rule["id"]
                result.rule_name = rule["name"]
                result.rule_type = rule_type
                result.execution_time = time.time() - start

                # Track API failures
                if result.status == "error" and rule_type in ("api", "external_data"):
                    api_name = rule.get("config", {}).get("api", {}).get("name") or \
                               rule.get("config", {}).get("external_api", {}).get("name", "")
                    api_failure_counts[api_name] = api_failure_counts.get(api_name, 0) + 1

                results.append({
                    "rule_id": result.rule_id,
                    "rule_name": result.rule_name,
                    "rule_type": result.rule_type,
                    "status": result.status,
                    "location": result.location,
                    "message": result.message,
                    "suggestion": result.suggestion,
                    "example": result.example,
                    "confidence": result.confidence,
                    "execution_time": result.execution_time,
                })

            # Step 4: Save results
            await self.db.update_task_progress(task_id, 95)
            await self.db.save_check_results(task_id, results)
            await self.db.update_task_status(task_id, TaskStatus.COMPLETED)

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await self.db.update_task_status(task_id, TaskStatus.FAILED, error=str(e))
```

- [ ] **Step 3: Write worker tests**

`tests/test_worker/test_worker.py`:
```python
import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock

from report_check.storage.database import Database, TaskStatus
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker
from report_check.models.manager import ModelManager


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database(str(tmp_path / "test.db"))


@pytest.fixture
def task_queue() -> TaskQueue:
    return TaskQueue()


class TestBackgroundWorker:
    @pytest.mark.asyncio
    async def test_process_text_check_task(self, db, task_queue, sample_excel_path):
        """End-to-end: enqueue a task with text rule, process, verify results."""
        rules = {
            "rules": [
                {"id": "r1", "name": "check keyword", "type": "text",
                 "config": {"keywords": ["交付内容"], "match_mode": "any"}}
            ]
        }
        await db.create_task(
            task_id="t1",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )
        await task_queue.enqueue("t1")

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)
        # Process one task directly
        await worker._process_task("t1")

        task = await db.get_task("t1")
        assert task["status"] == "completed"

        results = await db.get_check_results("t1")
        assert len(results) == 1
        assert results[0]["status"] == "passed"

    @pytest.mark.asyncio
    async def test_process_task_invalid_file_fails(self, db, task_queue, tmp_path):
        """Task with nonexistent file should fail gracefully."""
        rules = {"rules": [{"id": "r1", "name": "t", "type": "text", "config": {"keywords": ["x"]}}]}
        await db.create_task(
            task_id="t2",
            file_name="missing.xlsx",
            file_path=str(tmp_path / "missing.xlsx"),
            rules=rules,
        )

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)
        await worker._process_task("t2")

        task = await db.get_task("t2")
        assert task["status"] == "failed"
        assert task["error"] is not None

    @pytest.mark.asyncio
    async def test_crash_recovery(self, db, task_queue, sample_excel_path):
        """Processing tasks should be re-enqueued on startup."""
        rules = {"rules": []}
        await db.create_task(
            task_id="t3",
            file_name="test.xlsx",
            file_path=str(sample_excel_path),
            rules=rules,
        )
        await db.update_task_status("t3", TaskStatus.PROCESSING)

        mm = ModelManager(default_provider="fake")
        worker = BackgroundWorker(db=db, model_manager=mm, task_queue=task_queue)

        # Simulate startup recovery (without starting the run loop)
        recovered = await db.recover_orphaned_tasks()
        for tid in recovered:
            await task_queue.enqueue(tid)

        assert task_queue.size() == 1
```

- [ ] **Step 4: Run worker tests**

```bash
uv run pytest tests/test_worker/test_worker.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/report_check/worker/ tests/test_worker/
git commit -m "feat: task queue and background worker with crash recovery and circuit breaker"
```

---

### Task 11: API Layer (Router + Schemas + Main App)

**Files:**
- Create: `src/report_check/api/schemas.py`
- Create: `src/report_check/api/router.py`
- Create: `src/report_check/main.py`
- Test: `tests/test_api/test_router.py`

- [ ] **Step 1: Implement Pydantic schemas**

`src/report_check/api/schemas.py`:
```python
from pydantic import BaseModel, Field
from typing import Any


class CheckSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str


class LocationInfo(BaseModel):
    type: str = ""
    value: str = ""
    context: str = ""


class CheckResultItem(BaseModel):
    rule_id: str
    rule_name: str
    rule_type: str
    status: str
    location: LocationInfo = LocationInfo()
    message: str = ""
    suggestion: str = ""
    example: str = ""
    confidence: float = 1.0


class CheckSummary(BaseModel):
    total: int
    passed: int
    failed: int
    error: int


class CheckResultData(BaseModel):
    report_info: dict[str, Any]
    results: list[CheckResultItem]
    summary: CheckSummary


class CheckResultResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    result: CheckResultData | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    queue_size: int
    version: str


class ValidationError(BaseModel):
    rule_id: str
    field: str
    message: str


class RuleValidateResponse(BaseModel):
    valid: bool
    errors: list[ValidationError] = []


class ErrorResponse(BaseModel):
    error: dict[str, str]
```

- [ ] **Step 2: Implement router**

`src/report_check/api/router.py`:
```python
import json
import uuid
import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from typing import Optional

from report_check.api.schemas import (
    CheckResultItem,
    CheckResultResponse,
    CheckResultData,
    CheckSubmitResponse,
    CheckSummary,
    HealthResponse,
    LocationInfo,
    RuleValidateResponse,
    ValidationError,
)
from report_check.core.exceptions import CheckError
from report_check.engine.validator import RuleValidator
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
limiter = Limiter(key_func=get_remote_address)

EXCEL_MAGIC = b"PK"  # .xlsx files are ZIP-based
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    return HealthResponse(
        status="ok",
        queue_size=request.app.state.task_queue.size(),
        version="1.0.0",
    )


@router.post("/check/submit", response_model=CheckSubmitResponse)
@limiter.limit("10/minute")
async def submit_check(
    request: Request,
    file: UploadFile = File(...),
    rules: str = Form(...),
    report_type: Optional[str] = Form(None),
    context_vars: Optional[str] = Form(None),
):
    # Validate file extension
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    # Read file
    file_data = await file.read()

    # Validate file size
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 20MB 限制")

    # Validate magic bytes
    if not file_data[:2] == EXCEL_MAGIC:
        raise HTTPException(status_code=400, detail="文件格式不合法")

    # Parse rules
    try:
        rules_dict = json.loads(rules)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="规则 DSL 必须是有效的 JSON")

    # Validate rules
    validator = RuleValidator()
    validation = validator.validate(rules_dict)
    if not validation.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"规则验证失败: {validation.errors}",
        )

    # Parse context_vars
    ctx_vars = None
    if context_vars:
        try:
            ctx_vars = json.loads(context_vars)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="context_vars 必须是有效的 JSON")

    # Save file
    task_id = str(uuid.uuid4())
    file_path = await request.app.state.file_storage.save_uploaded_file(
        file_data, file.filename, task_id
    )

    # Create task
    await request.app.state.db.create_task(
        task_id=task_id,
        file_name=file.filename,
        file_path=file_path,
        rules=rules_dict,
        report_type=report_type,
        context_vars=ctx_vars,
    )

    # Enqueue
    await request.app.state.task_queue.enqueue(task_id)

    return CheckSubmitResponse(
        task_id=task_id,
        status="pending",
        message="任务已提交，正在排队处理",
    )


@router.get("/check/result/{task_id}", response_model=CheckResultResponse)
async def get_check_result(request: Request, task_id: str):
    task = await request.app.state.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    response = CheckResultResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
    )

    if task["status"] == "completed":
        results = await request.app.state.db.get_check_results(task_id)
        items = [
            CheckResultItem(
                rule_id=r["rule_id"],
                rule_name=r["rule_name"],
                rule_type=r["rule_type"],
                status=r["status"],
                location=LocationInfo(**r["location"]) if r["location"] else LocationInfo(),
                message=r.get("message", ""),
                suggestion=r.get("suggestion", ""),
                example=r.get("example", ""),
                confidence=r.get("confidence", 1.0),
            )
            for r in results
        ]
        summary = CheckSummary(
            total=len(items),
            passed=sum(1 for i in items if i.status == "passed"),
            failed=sum(1 for i in items if i.status == "failed"),
            error=sum(1 for i in items if i.status == "error"),
        )
        response.result = CheckResultData(
            report_info={
                "file_name": task["file_name"],
                "report_type": task.get("report_type"),
            },
            results=items,
            summary=summary,
        )

    if task["status"] == "failed":
        response.error = task.get("error")

    return response


@router.post("/rules/validate", response_model=RuleValidateResponse)
async def validate_rules(rules: dict):
    validator = RuleValidator()
    result = validator.validate(rules)
    return RuleValidateResponse(
        valid=result.is_valid,
        errors=[
            ValidationError(**e) for e in result.errors
        ],
    )


@router.get("/templates")
async def list_templates(request: Request, report_type: str | None = None):
    templates = await request.app.state.db.get_rule_templates(report_type)
    return {"templates": templates}


@router.get("/templates/{template_id}")
async def get_template(request: Request, template_id: int):
    template = await request.app.state.db.get_rule_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template
```

- [ ] **Step 3: Implement main.py**

`src/report_check/main.py`:
```python
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from report_check.api.router import router
from report_check.core.config import load_config
from report_check.core.exceptions import CheckError
from report_check.models.manager import ModelManager
from report_check.models.openai_adapter import OpenAIAdapter
from report_check.models.qwen_adapter import QwenAdapter
from report_check.storage.database import Database
from report_check.storage.file import FileStorage
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load config
    config_path = Path("config/models.yaml")
    if config_path.exists():
        model_config = load_config(str(config_path))
    else:
        model_config = {"default_provider": "openai", "providers": {}}

    app_config_path = Path("config/app.yaml")
    if app_config_path.exists():
        app_config = load_config(str(app_config_path))
    else:
        app_config = {"storage": {"database_path": "data/reports.db", "upload_path": "data/uploads"}}

    storage_config = app_config.get("storage", {})

    # Ensure data directories
    Path(storage_config.get("database_path", "data/reports.db")).parent.mkdir(parents=True, exist_ok=True)

    # Init components
    app.state.db = Database(storage_config.get("database_path", "data/reports.db"))
    app.state.file_storage = FileStorage(storage_config.get("upload_path", "data/uploads"))
    app.state.task_queue = TaskQueue()

    # Init model manager
    model_manager = ModelManager(
        default_provider=model_config.get("default_provider", "openai")
    )
    for name, cfg in model_config.get("providers", {}).items():
        if name == "openai":
            model_manager.register_adapter(name, OpenAIAdapter(cfg))
        elif name == "qwen":
            model_manager.register_adapter(name, QwenAdapter(cfg))

    app.state.model_manager = model_manager

    # Start worker
    app.state.worker = BackgroundWorker(
        db=app.state.db,
        model_manager=model_manager,
        task_queue=app.state.task_queue,
    )
    await app.state.worker.start()

    yield

    await app.state.worker.stop()


app = FastAPI(
    title="报告一致性检查系统",
    description="AI 驱动的 Excel 报告自动检查服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)


@app.exception_handler(CheckError)
async def check_error_handler(request: Request, exc: CheckError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
```

- [ ] **Step 4: Write API integration test**

`tests/test_api/test_router.py`:
```python
import json
import pytest
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient

from report_check.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestSubmitEndpoint:
    def test_submit_valid(self, client, sample_excel_path):
        rules = json.dumps({
            "rules": [
                {"id": "r1", "name": "test", "type": "text", "config": {"keywords": ["交付"]}}
            ]
        })
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"rules": rules},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"

    def test_submit_invalid_extension(self, client):
        resp = client.post(
            "/api/v1/check/submit",
            files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
            data={"rules": "{}"},
        )
        assert resp.status_code == 400

    def test_submit_invalid_rules(self, client, sample_excel_path):
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"rules": "not json"},
            )
        assert resp.status_code == 400


class TestResultEndpoint:
    def test_result_not_found(self, client):
        resp = client.get("/api/v1/check/result/nonexistent")
        assert resp.status_code == 404


class TestValidateEndpoint:
    def test_validate_valid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1", "name": "t", "type": "text", "config": {"keywords": ["x"]}}]},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True

    def test_validate_invalid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1"}]},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is False
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_api/test_router.py -v
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/report_check/api/ src/report_check/main.py tests/test_api/
git commit -m "feat: FastAPI app with all endpoints, schemas, and CORS"
```

---

### Task 12: Docker and Final Integration

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yaml`
- Create: `.gitignore`

- [ ] **Step 1: Create Dockerfile**

`Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY config/ config/

RUN mkdir -p data logs

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "report_check.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: Create docker-compose.yaml**

`docker-compose.yaml`:
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - QWEN_API_KEY=${QWEN_API_KEY}
      - MODEL_PROVIDER=${MODEL_PROVIDER:-openai}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```

- [ ] **Step 3: Create .gitignore**

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
data/
logs/
*.egg-info/
dist/
.pytest_cache/
.env
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -v
```

Expected: All PASS

- [ ] **Step 5: Test local server startup**

```bash
uv run uvicorn report_check.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl http://localhost:8000/api/v1/health
kill %1
```

Expected: `{"status":"ok","queue_size":0,"version":"1.0.0"}`

- [ ] **Step 6: Commit**

```bash
git add Dockerfile docker-compose.yaml .gitignore
git commit -m "feat: Docker deployment configuration"
```

---

## Task Dependency Summary

```
Task 1 (Scaffolding)
  └── Task 2 (Excel Parser)
        └── Task 3 (Summarizer)
  └── Task 4 (Storage)
  └── Task 5 (Model Layer)
  └── Task 6 (Rule Engine)
        └── Task 7 (TextChecker)
              └── Task 8 (Semantic + Image Checkers)
                    └── Task 9 (API + External Checkers)
  └── Task 10 (Worker) — depends on Tasks 4, 5, 6, 7-9
        └── Task 11 (API Layer) — depends on all above
              └── Task 12 (Docker + Integration)
```

Tasks 2, 4, 5, 6 can be parallelized after Task 1. Task 3 depends on Task 2.
Tasks 7-9 are sequential (each builds on the previous checker).
Tasks 10-12 are sequential (each depends on the previous).
