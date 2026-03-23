---
name: PDF Report Checking Feature
description: Add PDF report parsing and checking capability to the existing Excel-based report checking system
type: feature
---

# PDF 报告检查功能设计文档

## 1. 概述

### 1.1 目标

在现有的 Excel 报告检查系统基础上，新增 PDF 报告的解析和检查能力，支持图文混排的 PDF 文档，复用现有的五种检查器（text、semantic、image、api、external_data）。

### 1.2 需求确认

- **PDF 类型**: 图文混排的 PDF（既有文字说明，也有图表、图片等可视化内容）
- **检查类型**: 全部支持（text、semantic、image、api、external_data）
- **定位方式**: AI 自由定位（用户通过语义描述定位内容，无需指定页码或坐标）
- **解析策略**: 结构化文本提取 + 独立图片提取（先验证效果，效果不好再调整）

### 1.3 实现方案

采用**方案二：并行 Parser 抽象**

引入 `BaseParser` 抽象接口，`ExcelParser` 和 `PDFParser` 并行实现。通过统一的 `ReportData` 数据模型，让所有现有 Checker 无需修改即可支持 PDF。

**核心优势：**
- 架构清晰，扩展性好（未来可轻松加入 Word/PPT 解析）
- 所有现有 Checker 零修改，完全复用
- 数据模型通用化，不受 Excel 概念约束

---

## 2. 数据模型调整

### 2.1 ContentBlock（原 CellData）

将 `CellData` 重命名为 `ContentBlock`，字段更通用化：

```python
@dataclass
class ContentBlock:
    position: int       # Excel: 行号, PDF: 页码
    index: int          # Excel: 列号, PDF: 块序号
    content: Any        # 内容
    content_type: str   # Excel: "s"(字符串)/"n"(数字)/"b"(布尔)/"d"(日期)
                        # PDF: "s"(文本，统一使用字符串类型)
    ref: str            # 可读标识（Excel: "A1", PDF: "P3.B5"）
```

**设计理由：**
- `position`/`index` 用于编程计算（范围查询、坐标运算）
- `ref` 用于展示和 AI prompt（预计算的格式化字符串）
- 三个位置字段各司其职，避免下游重复格式转换

### 2.2 ReportData 调整

```python
@dataclass
class ReportData:
    file_name: str
    source_type: str                    # "excel" | "pdf"
    blocks: list[ContentBlock]          # 原 cells
    images: list[ImageData]
    metadata: dict[str, Any]            # Excel: {sheet_name, row_count, col_count}
                                        # PDF: {page_count, author, title}
```

**主要变化：**
- `cells` → `blocks`（配合 ContentBlock 更名）
- `sheet_name` 移入 `metadata`（PDF 没有工作表概念）
- 新增 `source_type` 字段（让下游区分来源格式）

### 2.3 ImageData 调整

```python
@dataclass
class ImageData:
    id: str
    data: bytes
    format: str
    anchor: dict                        # Excel: {"row": 1, "col": 1, "cell_ref": "A1"}
                                        # PDF: {"page": 3, "cell_ref": "P3", "index": 0}
    nearby_blocks: list[ContentBlock]   # 原 nearby_cells
```

---

## 3. Parser 抽象层

### 3.1 BaseParser 接口

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

**工厂方法设计：**
- `for_file` 是类方法，放在 `BaseParser` 上
- `BackgroundWorker` 只需改一行：`parser = BaseParser.for_file(task["file_path"])`

### 3.2 ExcelParser 改造

继承 `BaseParser`，调整返回值：
- `cells` → `blocks`（构造 `ContentBlock` 对象）
- `sheet_name` 移入 `metadata`
- 新增 `source_type="excel"`

### 3.3 PDFParser 实现

```python
import pdfplumber
from pathlib import Path
from PIL import Image
from io import BytesIO

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
```

**文本提取策略：**
```python
def _extract_blocks(self, doc) -> list[ContentBlock]:
    blocks = []
    total_text_length = 0

    for page_num, page in enumerate(doc.pages, start=1):
        try:
            text = page.extract_text()
            if not text or not text.strip():
                continue  # 跳过空白页

            total_text_length += len(text.strip())

            # 按段落分块（简单策略：按双换行符分割）
            # 如果没有双换行符，按单换行符分割
            paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in text.split('\n') if p.strip()]

            for block_idx, para in enumerate(paragraphs, start=1):
                blocks.append(ContentBlock(
                    position=page_num,
                    index=block_idx,
                    content=para,
                    content_type="s",
                    ref=f"P{page_num}.B{block_idx}",
                ))
        except Exception as e:
            logger.warning(f"第 {page_num} 页文本提取失败: {e}")
            continue

    if not blocks:
        raise ValueError("PDF 中未提取到任何文本内容")

    # 检测扫描件 PDF（文本层过少）
    avg_text_per_page = total_text_length / len(doc.pages) if doc.pages else 0
    if avg_text_per_page < 50:  # 平均每页少于 50 字符，可能是扫描件
        logger.warning(f"PDF 可能是扫描件（平均每页 {avg_text_per_page:.1f} 字符）")
        raise ValueError("PDF 可能是扫描件，需要 OCR 识别（当前不支持）")

    return blocks
```

**效果验证标准：**
当出现以下情况时，认为"效果不好"，需要升级为页面渲染方案：
- 用户反馈定位准确率低于 70%（连续 10 个任务中有 3 个以上定位失败）
- 复杂排版（多栏、表格）导致文本顺序混乱，AI 无法理解语义
- 图表与文字关联错误（nearby_blocks 不相关）

**图片提取策略：**
```python
def _extract_images(self, doc, blocks: list[ContentBlock]) -> list[ImageData]:
    """提取 PDF 中的嵌入图片

    注意：pdfplumber 0.11.0 的 page.images 返回字典列表，每个字典包含：
    - 'x0', 'y0', 'x1', 'y1': 图片坐标
    - 'width', 'height': 尺寸
    - 'name': 图片名称
    - 'stream': PIL.PdfImagePlugin.PdfImageFile 对象（需调用 .convert() 获取字节）
    """
    images = []
    for page_num, page in enumerate(doc.pages, start=1):
        try:
            page_images = page.images
            for img_idx, img_info in enumerate(page_images):
                # pdfplumber 的 images 是字典，包含 'stream' 键
                # stream 是 PIL Image 对象，需要转换为字节
                try:
                    from io import BytesIO
                    img_obj = img_info.get("stream")
                    if img_obj is None:
                        continue

                    # 将 PIL Image 转换为字节
                    buf = BytesIO()
                    img_obj.save(buf, format='PNG')
                    img_bytes = buf.getvalue()
                except Exception as e:
                    logger.warning(f"图片 {img_idx} 转换失败: {e}")
                    continue

                fmt = self._detect_and_convert_format(img_bytes)
                if fmt is None:
                    continue

                # 获取同页文本块作为 nearby_blocks（取前 5 个）
                # 选择策略：简单取同页前 5 个块，未来可根据坐标优化
                nearby = [b for b in blocks if b.position == page_num][:5]

                images.append(ImageData(
                    id=f"img_p{page_num}_{img_idx}",
                    data=img_bytes if fmt[1] is None else fmt[1],
                    format=fmt[0],
                    anchor={"page": page_num, "cell_ref": f"P{page_num}", "index": img_idx},
                    nearby_blocks=nearby,
                ))
        except Exception as e:
            logger.warning(f"第 {page_num} 页图片提取失败: {e}")
            continue

    return images

def _detect_and_convert_format(self, data: bytes) -> tuple[str, bytes | None] | None:
    """复用 ExcelParser 的图片格式检测和转换逻辑"""
    # 与 ExcelParser._detect_and_convert_format 相同
```

### 3.4 PDF 解析库选型

选择 **pdfplumber** 而不是 pypdf / pymupdf：
- 同时支持文本提取和图片提取，一个库搞定
- 文本提取保留位置信息（坐标），方便未来升级为坐标定位
- 纯 Python，无系统依赖，Docker 部署简单
- 依赖包新增：`pdfplumber>=0.11.0`

---

## 4. ReportSummarizer 适配

### 4.1 根据 source_type 分发

```python
class ReportSummarizer:
    def summarize(self, report_data: ReportData) -> str:
        if report_data.source_type == "excel":
            return self._summarize_excel(report_data)
        elif report_data.source_type == "pdf":
            return self._summarize_pdf(report_data)
        else:
            raise ValueError(f"Unknown source_type: {report_data.source_type}")
```

### 4.2 Excel 摘要（原逻辑）

```python
def _summarize_excel(self, report_data: ReportData) -> str:
    lines = []
    lines.append(f"工作表: {report_data.metadata.get('sheet_name', '未知')}")
    lines.append(f"行数: {report_data.metadata.get('row_count', 0)}, 列数: {report_data.metadata.get('col_count', 0)}")
    lines.append("")

    # 按 position (行号) 分组
    rows = {}
    for block in report_data.blocks:
        rows.setdefault(block.position, []).append(block)

    for row_num in sorted(rows.keys()):
        row_blocks = sorted(rows[row_num], key=lambda b: b.index)
        parts = [f"{b.ref}: {self._truncate(b.content)}" for b in row_blocks]
        lines.append(" | ".join(parts))
        if len("\n".join(lines)) >= self.max_summary_length:
            lines.append("... (内容已截断)")
            break

    # 图片信息
    if report_data.images:
        lines.append(f"\n=== 图片 ({len(report_data.images)} 张) ===")
        for img in report_data.images:
            anchor_ref = img.anchor.get("cell_ref", "未知")
            nearby = ", ".join(str(b.content) for b in img.nearby_blocks[:5])
            lines.append(f"  {img.id} 位置: {anchor_ref}, 附近: {nearby}")

    return "\n".join(lines)
```

### 4.3 PDF 摘要

```python
def _summarize_pdf(self, report_data: ReportData) -> str:
    lines = []
    lines.append(f"PDF 文件: {report_data.file_name}")
    lines.append(f"页数: {report_data.metadata.get('page_count', 0)}")
    if report_data.metadata.get('title'):
        lines.append(f"标题: {report_data.metadata['title']}")
    lines.append("")

    # 按 position (页码) 分组
    pages = {}
    for block in report_data.blocks:
        pages.setdefault(block.position, []).append(block)

    for page_num in sorted(pages.keys()):
        lines.append(f"=== 第 {page_num} 页 ===")
        page_blocks = sorted(pages[page_num], key=lambda b: b.index)
        for block in page_blocks:
            lines.append(f"{block.ref}: {self._truncate(block.content)}")
        lines.append("")
        if len("\n".join(lines)) >= self.max_summary_length:
            lines.append("... (内容已截断)")
            break

    # 图片信息
    if report_data.images:
        lines.append(f"=== 图片 ({len(report_data.images)} 张) ===")
        for img in report_data.images:
            page = img.anchor.get("page", "?")
            nearby = ", ".join(str(b.content) for b in img.nearby_blocks[:3])
            lines.append(f"  {img.id} 第{page}页, 附近: {nearby}")

    return "\n".join(lines)
```

### 4.4 get_region 方法适配

```python
def get_region(self, report_data: ReportData, start_pos: int, end_pos: int) -> str:
    """提取指定位置范围的内容

    Excel: start_pos/end_pos 是行号
    PDF: start_pos/end_pos 是页码
    """
    lines = []
    positions = {}
    for block in report_data.blocks:
        if start_pos <= block.position <= end_pos:
            positions.setdefault(block.position, []).append(block)

    for pos in sorted(positions.keys()):
        blocks = sorted(positions[pos], key=lambda b: b.index)
        parts = [f"{b.ref}: {b.content}" for b in blocks]
        lines.append(" | ".join(parts))

    result = "\n".join(lines)
    if len(result) > self.max_region_length:
        result = result[:self.max_region_length] + "\n... (已截断)"
    return result
```

---

## 5. BaseChecker.locate_content 适配

### 5.1 Prompt 调整

```python
async def locate_content(self, description: str, context_hint: Optional[str] = None) -> Optional[list]:
    from report_check.parser.summarizer import ReportSummarizer
    summarizer = ReportSummarizer()
    report_summary = summarizer.summarize(self.report_data)

    source_label = "Excel 报告" if self.report_data.source_type == "excel" else "PDF 报告"
    location_field = "sheet" if self.report_data.source_type == "excel" else "page"
    location_desc = "工作表名" if self.report_data.source_type == "excel" else "页码"

    # 根据 source_type 调整 JSON 格式示例
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

{report_summary}

请在上述报告中找出符合以下描述的内容：
描述：{description}
{f'提示：{context_hint}' if context_hint else ''}

请以 JSON 格式回复，格式如下：
{{
  "found": true/false,
  "locations": [{location_example}
  ]
}}

只返回 JSON，不要有其他文字。"""

    # ... 后续逻辑不变
```

---

## 6. API 层和文件验证调整

### 6.1 文件类型验证（router.py）

```python
EXCEL_MAGIC = b"PK"
PDF_MAGIC = b"%PDF"
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB

@router.post("/check/submit", response_model=CheckSubmitResponse)
async def submit_check(
    request: Request,
    file: UploadFile = File(...),
    rules: str = Form(...),
    report_type: Optional[str] = Form(None),
    context_vars: Optional[str] = Form(None),
):
    # 验证文件扩展名
    if not file.filename or not file.filename.endswith((".xlsx", ".xls", ".pdf")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx, .xls 或 .pdf 文件")

    file_data = await file.read()

    # 验证文件大小
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 20MB 限制")

    # 验证 magic bytes
    if not (file_data[:2] == EXCEL_MAGIC or file_data[:4] == PDF_MAGIC):
        raise HTTPException(status_code=400, detail="文件格式不合法")

    # ... 后续逻辑不变
```

### 6.2 BackgroundWorker 修改（worker.py）

```python
async def _process_task(self, task_id: str):
    task = await self.db.get_task(task_id)
    if not task:
        logger.warning(f"Task not found: {task_id}")
        return

    try:
        await self.db.update_task_status(task_id, TaskStatus.PROCESSING)

        # Step 1: Parse file
        await self.db.update_task_progress(task_id, 10)
        try:
            parser = BaseParser.for_file(task["file_path"])
            report_data = parser.parse(task["file_path"])
        except ValueError as e:
            # PDF 特定错误（扫描件、加密等）
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

        # Step 2-4: 完全不变，所有 Checker 直接复用
        # ...
```

---

## 7. 错误处理和边界情况

### 7.1 PDF 解析异常

| 情况 | 处理策略 |
|---|---|
| PDF 全是扫描图片（无文本层） | `_extract_blocks` 返回空，抛出 `ValueError("PDF 中未提取到任何文本内容")`，任务标记为 failed |
| PDF 加密/有密码保护 | `pdfplumber.open` 抛异常，捕获后转为 `ValueError`，任务 failed |
| PDF 某页损坏 | 跳过该页，记录 warning，继续处理其他页 |
| PDF 无嵌入图片 | `images` 返回空列表，不影响文本检查 |
| 用户上传的 PDF 实际是图片 | magic bytes 验证会拦截（`%PDF` 不匹配） |

### 7.2 Checker 兼容性验证

所有现有 Checker 无需修改即可工作：

- **TextChecker**: 调用 `report_data.search_text()`，遍历 `blocks`，返回 `ContentBlock` 对象，`location` 字段包含 `ref="P3.B5"`
- **SemanticChecker**: 调用 `locate_content()`，AI 返回的 `locations` 中 `cell` 字段改为 `ref`，`cell_range` 可选
- **ImageChecker**: 遍历 `report_data.images`，`nearby_blocks` 提供上下文
- **ApiChecker / ExternalDataChecker**: 依赖 `locate_content()` 找到数据位置，然后提取 `content` 进行比对

---

## 8. 依赖包变更

### 8.1 pyproject.toml

```toml
dependencies = [
    # ... 现有依赖
    "pdfplumber>=0.11.0",  # 新增
]
```

---

## 9. 实施计划

### 9.1 文件修改清单

| 文件 | 修改内容 |
|---|---|
| `parser/models.py` | `CellData` → `ContentBlock`，`ReportData` 调整 |
| `parser/base.py` | **新增** `BaseParser` 抽象类 |
| `parser/excel.py` | 继承 `BaseParser`，适配新数据模型 |
| `parser/pdf.py` | **新增** `PDFParser` 实现 |
| `parser/summarizer.py` | 新增 `_summarize_pdf` 方法，`get_region` 适配 |
| `checkers/base.py` | `locate_content` prompt 适配 |
| `api/router.py` | 文件类型验证放宽 |
| `worker/worker.py` | `BaseParser.for_file()` + PDF 错误处理 |
| `pyproject.toml` | 新增 `pdfplumber` 依赖 |

### 9.2 测试策略

1. **单元测试**
   - `PDFParser.parse()` 测试（正常 PDF、空白页、无图片）
   - `ReportSummarizer._summarize_pdf()` 测试
   - `ContentBlock` 数据模型测试

2. **集成测试**
   - 上传 PDF 文件 → 任务创建 → Worker 处理 → 结果返回
   - 五种 Checker 在 PDF 上的运行测试

3. **边界测试**
   - 扫描件 PDF（无文本层）
   - 加密 PDF
   - 损坏的 PDF

### 9.3 实施步骤

1. 数据模型重构（`ContentBlock`、`ReportData`）
2. Parser 抽象层（`BaseParser`、`ExcelParser` 改造）
3. `PDFParser` 实现
4. `ReportSummarizer` 适配
5. `BaseChecker.locate_content` 适配
6. API 层调整
7. 测试验证
8. 文档更新

---

## 10. 未来扩展

### 10.1 升级为页面渲染方案

如果结构化文本提取效果不佳，可升级为方案 B（将每页渲染成图片）：
- 新增 `PDFImageParser`，使用 `pdf2image` 或 `pymupdf` 渲染
- 修改 `BaseParser.for_file()` 增加配置项选择 Parser
- 无需修改 Checker 层

### 10.2 支持其他文档格式

- **Word (.docx)**: 使用 `python-docx` 提取段落和图片
- **PPT (.pptx)**: 使用 `python-pptx` 提取幻灯片内容
- 只需新增对应 Parser，实现 `BaseParser` 接口

### 10.3 坐标定位增强

当前 PDF 定位完全依赖 AI 语义理解，未来可增强为：
- 用户可选"页码 + 坐标区域"定位
- `pdfplumber` 已提供文本坐标信息，可在 `ContentBlock` 的 `metadata` 中保存
- 规则 DSL 增加 `location_mode: "semantic" | "coordinate"` 配置

---

## 11. 风险和限制

### 11.1 已知限制

- **扫描件 PDF**: 无文本层的 PDF 无法处理，需要 OCR（未来可集成 Tesseract）
- **复杂排版**: 多栏、文字环绕图表等复杂排版可能提取顺序混乱
- **表格识别**: `pdfplumber` 对表格的识别有限，可能需要专门的表格提取逻辑

### 11.2 性能考虑

- PDF 解析比 Excel 慢（尤其是大文件）
- 图片提取会增加内存占用
- 建议保持 20MB 文件大小限制

### 11.3 AI Token 消耗

- PDF 摘要通常比 Excel 更长（段落文本 vs 单元格）
- `locate_content` 的 Token 消耗可能增加 20-50%
- 建议监控 AI 调用成本

---

## 12. 总结

本设计通过引入 `BaseParser` 抽象和通用化的 `ContentBlock` 数据模型，实现了 PDF 报告检查功能，同时保持了架构的清晰性和扩展性。所有现有 Checker 无需修改即可支持 PDF，验证了设计的合理性。

**核心优势：**
- 最小化代码改动（仅 9 个文件）
- 完全复用现有 Checker 逻辑
- 为未来扩展（Word、PPT）奠定基础
- 保持了系统的简洁性和可维护性
