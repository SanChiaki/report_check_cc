# PDF 报告检查功能实施计划

**基于设计文档**: `docs/superpowers/specs/2026-03-23-pdf-report-checking-design.md`

**目标**: 在现有 Excel 报告检查系统基础上，新增 PDF 报告解析和检查能力，支持图文混排的 PDF 文档。

---

## 实施步骤概览

本计划分为 8 个主要步骤，按依赖关系顺序执行：

1. **添加依赖包** - 在 pyproject.toml 中添加 pdfplumber
2. **数据模型重构** - CellData → ContentBlock，ReportData 调整
3. **提取共享工具函数** - _detect_and_convert_format 到 parser/utils.py
4. **Parser 抽象层** - BaseParser + ExcelParser 改造
5. **PDFParser 实现** - 新增 PDF 解析器
6. **ReportSummarizer 适配** - 支持 PDF 摘要生成
7. **Checker 层适配** - 所有 Checker 的字段重命名和 source_type 分发
8. **API 和 Worker 层调整** - 文件验证和错误处理

每个步骤完成后需要运行相关测试验证。

---

## 步骤 1: 添加依赖包

**文件**: `pyproject.toml`

**操作**: 在 `dependencies` 列表中添加 `pdfplumber>=0.11.0`

**验证**: 运行 `uv sync` 确保依赖安装成功

---

## 步骤 2: 数据模型重构

### 2.1 重命名 CellData 为 ContentBlock

**文件**: `src/report_check/parser/models.py`

**修改内容**:

```python
# 将 CellData 类重命名为 ContentBlock
@dataclass
class ContentBlock:
    position: int       # 原 row
    index: int          # 原 col
    content: Any        # 原 value
    content_type: str   # 原 data_type
    ref: str            # 原 cell_ref
```

**字段映射**:
- `row` → `position`
- `col` → `index`
- `value` → `content`
- `data_type` → `content_type`
- `cell_ref` → `ref`

### 2.2 调整 ReportData

**修改内容**:

```python
@dataclass
class ReportData:
    file_name: str
    source_type: str = "excel"          # 新增字段
    blocks: list[ContentBlock]          # 原 cells
    images: list[ImageData]
    metadata: dict[str, Any]            # sheet_name 移入此处

    def search_text(self, keyword: str, case_sensitive: bool = False) -> list[ContentBlock]:
        # 更新字段引用: self.cells → self.blocks, cell.value → block.content

    def get_blocks_in_range(self, start_row: int, end_row: int, start_col: int, end_col: int) -> list[ContentBlock]:
        # 原 get_cells_in_range，更新字段引用
```

### 2.3 调整 ImageData

**修改内容**:

```python
@dataclass
class ImageData:
    id: str
    data: bytes
    format: str
    anchor: dict
    nearby_blocks: list[ContentBlock]   # 原 nearby_cells
```

**验证**: 运行 `uv run pytest tests/test_parser/test_excel.py -v` (会失败，因为 ExcelParser 还未更新)

---

## 步骤 3: 提取共享工具函数

**文件**: `src/report_check/parser/utils.py` (新建)

**内容**: 从 ExcelParser 提取 `detect_and_convert_format` 函数

```python
import logging
from io import BytesIO
from PIL import Image

logger = logging.getLogger(__name__)

MAX_IMAGE_SIZE = 2048

def detect_and_convert_format(data: bytes) -> tuple[str, bytes | None] | None:
    """检测图片格式并转换为支持的格式

    Returns:
        (format, converted_bytes) 或 None
        如果不需要转换，converted_bytes 为 None
    """
    try:
        pil_img = Image.open(BytesIO(data))
    except Exception:
        return None

    fmt = (pil_img.format or "PNG").lower()

    # 缩放过大图片
    if max(pil_img.size) > MAX_IMAGE_SIZE:
        pil_img.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return ("png", buf.getvalue())

    # 转换不支持的格式
    if fmt not in ("png", "jpeg", "jpg", "gif", "webp"):
        buf = BytesIO()
        pil_img.save(buf, format="PNG")
        return ("png", buf.getvalue())

    return (fmt, None)
```

**验证**: 无需测试，下一步会验证

---

## 步骤 4: Parser 抽象层

### 4.1 创建 BaseParser

**文件**: `src/report_check/parser/base.py` (新建)

**内容**:

```python
from abc import ABC, abstractmethod
from pathlib import Path
from report_check.parser.models import ReportData

class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> ReportData:
        """解析文件并返回统一的 ReportData 结构"""
        pass

    @classmethod
    def for_file(cls, file_path: str) -> "BaseParser":
        """根据文件扩展名返回对应 Parser 实例"""
        from report_check.parser.excel import ExcelParser
        from report_check.parser.pdf import PDFParser

        ext = Path(file_path).suffix.lower()
        parsers = {
            ".xlsx": ExcelParser,
            ".xls": ExcelParser,
            ".pdf": PDFParser,
        }
        if ext not in parsers:
            raise ValueError(f"不支持的文件类型: {ext}")
        return parsers[ext]()
```

### 4.2 改造 ExcelParser

**文件**: `src/report_check/parser/excel.py`

**修改内容**:

1. 继承 `BaseParser`
2. 导入 `from report_check.parser.base import BaseParser`
3. 导入 `from report_check.parser.utils import detect_and_convert_format`
4. 删除 `_detect_and_convert_format` 方法，改用 `detect_and_convert_format()`
5. 更新 `parse()` 返回值:
   - 构造 `ContentBlock` 而非 `CellData`
   - 添加 `source_type="excel"`
   - `sheet_name` 移入 `metadata`
6. 更新 `_extract_cells()` 返回 `list[ContentBlock]`
7. 更新 `_extract_images()` 中的 `nearby_cells` → `nearby_blocks`

**关键修改点**:

```python
class ExcelParser(BaseParser):
    def parse(self, file_path: str) -> ReportData:
        wb = openpyxl.load_workbook(file_path, data_only=True)
        ws = wb.active
        blocks = self._extract_cells(ws)
        images = self._extract_images(ws)
        return ReportData(
            file_name=Path(file_path).name,
            source_type="excel",
            blocks=blocks,
            images=images,
            metadata={
                "sheet_name": ws.title,
                "row_count": ws.max_row or 0,
                "col_count": ws.max_column or 0
            },
        )

    def _extract_cells(self, ws) -> list[ContentBlock]:
        blocks = []
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None:
                    blocks.append(ContentBlock(
                        position=cell.row,
                        index=cell.column,
                        content=str(cell.value),
                        content_type=cell.data_type or "s",
                        ref=cell.coordinate,
                    ))
        return blocks
```

**验证**: 运行 `uv run pytest tests/test_parser/test_excel.py -v` (需要先更新测试文件中的字段引用)

---

## 步骤 5: PDFParser 实现

**文件**: `src/report_check/parser/pdf.py` (新建)

**内容**: 完整实现 PDFParser 类，包括:
- `parse()` 主方法
- `_extract_blocks()` 文本提取
- `_extract_images()` 图片提取
- 扫描件检测逻辑

**关键实现** (参考设计文档 Section 3.3):

```python
import logging
import pdfplumber
from pathlib import Path
from io import BytesIO

from report_check.parser.base import BaseParser
from report_check.parser.models import ReportData, ContentBlock, ImageData
from report_check.parser.utils import detect_and_convert_format

logger = logging.getLogger(__name__)

class PDFParser(BaseParser):
    def parse(self, file_path: str) -> ReportData:
        try:
            doc = pdfplumber.open(file_path)
        except Exception as e:
            raise ValueError(f"无法打开 PDF 文件: {e}")

        try:
            blocks = self._extract_blocks(doc)
            images = self._extract_images(doc, blocks)
            metadata = {
                "page_count": len(doc.pages),
                "author": doc.metadata.get("Author", ""),
                "title": doc.metadata.get("Title", ""),
            }
        except Exception as e:
            doc.close()
            raise ValueError(f"PDF 解析失败: {e}")
        finally:
            doc.close()

        return ReportData(
            file_name=Path(file_path).name,
            source_type="pdf",
            blocks=blocks,
            images=images,
            metadata=metadata,
        )

    # _extract_blocks 和 _extract_images 实现见设计文档
```

**验证**: 创建 `tests/test_parser/test_pdf.py` 并运行测试

---

## 步骤 6: ReportSummarizer 适配

**文件**: `src/report_check/parser/summarizer.py`

**修改内容**:

1. 更新 `summarize()` 方法，根据 `source_type` 分发
2. 将现有逻辑重命名为 `_summarize_excel()`
3. 新增 `_summarize_pdf()` 方法
4. 更新 `get_region()` 方法的字段引用
5. 添加 `_truncate()` 辅助方法

**关键修改**:

```python
def summarize(self, report_data: ReportData) -> str:
    if report_data.source_type == "excel":
        return self._summarize_excel(report_data)
    elif report_data.source_type == "pdf":
        return self._summarize_pdf(report_data)
    else:
        raise ValueError(f"Unknown source_type: {report_data.source_type}")

def _summarize_excel(self, report_data: ReportData) -> str:
    # 原 summarize 逻辑，更新字段引用:
    # - report_data.cells → report_data.blocks
    # - cell.value → block.content
    # - img.nearby_cells → img.nearby_blocks

def _summarize_pdf(self, report_data: ReportData) -> str:
    # 见设计文档 Section 4.3
```

**验证**: 运行 `uv run pytest tests/test_parser/test_summarizer.py -v`

---

## 步骤 7: Checker 层适配

这是最复杂的步骤，需要更新 6 个 Checker 文件。

### 7.1 BaseChecker.locate_content 适配

**文件**: `src/report_check/checkers/base.py`

**修改内容**: 更新 `locate_content()` 方法的 prompt，根据 `source_type` 生成不同的 JSON 格式示例

**关键修改** (见设计文档 Section 5.1):

```python
async def locate_content(self, description: str, context_hint: Optional[str] = None) -> Optional[list]:
    # ... 前面代码不变

    source_label = "Excel 报告" if self.report_data.source_type == "excel" else "PDF 报告"

    if self.report_data.source_type == "excel":
        location_example = '''
    {
      "sheet": "工作表名",
      "cell": "A1",
      "cell_range": "A1:B3",
      "content": "找到的文本内容",
      "context": "上下文说明"
    }'''
    else:  # PDF
        location_example = '''
    {
      "page": 3,
      "ref": "P3.B5",
      "ref_range": "P3.B1:P3.B5",
      "content": "找到的文本内容",
      "context": "上下文说明"
    }'''

    prompt = f"""以下是{source_label}的内容摘要：
...
"""
```

### 7.2 TextChecker 适配

**文件**: `src/report_check/checkers/text.py`

**修改内容**: 无需修改逻辑，`search_text()` 已在 ReportData 中更新

**验证**: 运行 `uv run pytest tests/test_checkers/test_text.py -v`

### 7.3 SemanticChecker 适配

**文件**: `src/report_check/checkers/semantic.py`

**修改内容**: 更新 `_get_region_text()` 方法，根据 `source_type` 分发解析逻辑

**关键修改** (见设计文档 Section 7.2):

```python
def _get_region_text(self, summarizer: ReportSummarizer, location: dict) -> str:
    if self.report_data.source_type == "excel":
        cell_range = location.get("cell_range", "") or location.get("cell", "")
        try:
            from openpyxl.utils.cell import range_boundaries
            min_col, min_row, max_col, max_row = range_boundaries(cell_range)
            return summarizer.get_region(self.report_data, min_row, max_row)
        except Exception:
            return summarizer.summarize(self.report_data)
    else:  # PDF
        ref_range = location.get("ref_range", "") or location.get("ref", "")
        try:
            parts = ref_range.split(":")
            start_page = int(parts[0].split(".")[0].lstrip("P"))
            end_page = int(parts[-1].split(".")[0].lstrip("P"))
            return summarizer.get_region(self.report_data, start_page, end_page)
        except (ValueError, IndexError):
            return summarizer.summarize(self.report_data)
```

### 7.4 ImageChecker 适配

**文件**: `src/report_check/checkers/image.py`

**修改内容**: 更新 `_get_images()` 方法中的字段引用

```python
def _get_images(self, image_filter: dict) -> list:
    # ...
    for img in all_images:
        nearby_text = " ".join(str(c.content) for c in img.nearby_blocks)  # 原 c.value, img.nearby_cells
```

### 7.5 ApiChecker 适配

**文件**: `src/report_check/checkers/api_check.py`

**修改内容**: 更新 `_extract_text()` 方法，添加 source_type 分发 (同 SemanticChecker 模式)

### 7.6 ExternalDataChecker 适配

**文件**: `src/report_check/checkers/external.py`

**修改内容**: 更新 `_extract_data()` 方法，添加 source_type 分发 (同 SemanticChecker 模式)

**验证**: 运行 `uv run pytest tests/test_checkers/ -v`

---

## 步骤 8: API 和 Worker 层调整

### 8.1 API 路由调整

**文件**: `src/report_check/api/router.py`

**修改内容**:

1. 添加 `PDF_MAGIC = b"%PDF"`
2. 更新文件扩展名验证: `(".xlsx", ".xls", ".pdf")`
3. 更新 magic bytes 验证: `file_data[:2] == EXCEL_MAGIC or file_data[:4] == PDF_MAGIC`

### 8.2 BackgroundWorker 调整

**文件**: `src/report_check/worker/worker.py`

**修改内容**:

1. 导入 `from report_check.parser.base import BaseParser`
2. 更新 `_process_task()` 方法:
   - 将 `parser = ExcelParser()` 改为 `parser = BaseParser.for_file(task["file_path"])`
   - 添加 PDF 特定错误处理 (见设计文档 Section 6.2)

**关键修改**:

```python
try:
    parser = BaseParser.for_file(task["file_path"])
    report_data = parser.parse(task["file_path"])
except ValueError as e:
    error_msg = str(e)
    if "扫描件" in error_msg or "OCR" in error_msg:
        await self.db.update_task_status(
            task_id, TaskStatus.FAILED,
            error="PDF 是扫描件，需要 OCR 识别（当前不支持）"
        )
    elif "加密" in error_msg or "密码" in error_msg:
        await self.db.update_task_status(
            task_id, TaskStatus.FAILED,
            error="PDF 已加密，需要密码解锁"
        )
    else:
        await self.db.update_task_status(
            task_id, TaskStatus.FAILED,
            error=f"文件解析失败: {error_msg}"
        )
    return
```

**验证**: 运行 `uv run pytest tests/test_worker/test_worker.py -v`

---

## 测试策略

### 单元测试

创建以下测试文件:

1. `tests/test_parser/test_pdf.py` - PDFParser 测试
2. `tests/fixtures/sample.pdf` - 测试用 PDF 文件

### 集成测试

1. 创建包含文本和图片的测试 PDF
2. 通过 API 上传 PDF 并验证任务处理流程
3. 验证所有 5 种 Checker 在 PDF 上的运行

### 边界测试

1. 扫描件 PDF (无文本层)
2. 加密 PDF
3. 空白 PDF
4. 仅图片 PDF

---

## 实施顺序总结

1. ✅ 添加 pdfplumber 依赖
2. ✅ 数据模型重构 (ContentBlock, ReportData, ImageData)
3. ✅ 提取共享工具函数 (parser/utils.py)
4. ✅ Parser 抽象层 (BaseParser + ExcelParser 改造)
5. ✅ PDFParser 实现
6. ✅ ReportSummarizer 适配
7. ✅ Checker 层适配 (6 个文件)
8. ✅ API 和 Worker 层调整

每步完成后运行相关测试，确保功能正常。

---

## 注意事项

1. **字段重命名影响广泛**: 所有引用 `CellData` 字段的代码都需要更新
2. **测试文件同步更新**: 测试中的字段引用也需要更新 (如 `cell.value` → `block.content`)
3. **向后兼容**: 无需考虑，这是新功能，不影响现有 Excel 功能
4. **错误处理**: PDF 特定错误需要友好的错误消息
5. **性能**: PDF 解析比 Excel 慢，保持 20MB 文件大小限制

---

## 完成标准

- [ ] 所有单元测试通过
- [ ] 集成测试通过 (上传 PDF → 处理 → 返回结果)
- [ ] 边界测试通过 (扫描件、加密 PDF 正确报错)
- [ ] 现有 Excel 功能不受影响
- [ ] 代码 review 通过
- [ ] 文档更新 (CLAUDE.md 中的开发命令)
