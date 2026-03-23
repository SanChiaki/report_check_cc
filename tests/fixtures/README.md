# PDF 测试文件说明

本目录包含用于测试 PDF 报告检查功能的各种测试文件。

## 测试文件列表

### 1. telecom_report_normal.pdf (3KB)
**类型**: 正常 PDF（有文本层）

**内容**: 基于中国电信 5G 网络建设进展报告
- 包含项目信息、进展状态、风险提示等文本内容
- 有清晰的文本层，可以直接提取文字
- 用于测试结构化文本提取功能

**测试场景**:
- 文本检查（TextChecker）
- 语义检查（SemanticChecker）
- AI 定位功能（locate_content）

---

### 2. telecom_report_scanned.pdf (11MB)
**类型**: 扫描件 PDF（纯图片，无文本层）

**内容**: 模拟扫描的 5G 网络进展报告
- 整页渲染为图片，无可提取的文本层
- 包含噪点模拟扫描效果
- 平均每页文本量 < 50 字符（触发扫描件检测）

**测试场景**:
- 扫描件自动检测
- 页面渲染模式切换
- 多模态 AI 图片理解
- ImageChecker 功能

**注意**: 文件较大（11MB），未提交到 git。可通过运行 `python create_test_pdfs.py` 重新生成。

---

### 3. telecom_report_mixed.pdf (710KB)
**类型**: 混合 PDF（文本 + 嵌入图片）

**内容**: 包含文本和嵌入图片的综合报告
- 第一页：文本内容（项目信息、进展摘要）
- 第二页：嵌入的设备安装照片

**测试场景**:
- 文本和图片混合提取
- ImageChecker 对嵌入图片的检查
- nearby_blocks 关联测试

---

### 4. text_heavy.pdf (11KB)
**类型**: 文本密集型 PDF

**内容**: 技术规范文档，包含大量文本
- 多个章节，每章节多个段落
- 用于测试文本提取性能和摘要生成

**测试场景**:
- 大量文本的提取性能
- ReportSummarizer 的截断逻辑
- 文本搜索性能（search_text）

---

### 5. blank.pdf (0.5KB)
**类型**: 空白 PDF

**内容**: 只有一个空白页

**测试场景**:
- 边界测试：空白 PDF 的处理
- 错误处理：无内容时的行为
- 应该返回友好的错误消息

---

### 6. multipage_scanned.pdf (33MB)
**类型**: 多页扫描件 PDF

**内容**: 3 页扫描文档，每页独立渲染
- 测试多页扫描件的处理
- 每页都是独立的图片

**测试场景**:
- 多页扫描件的批量渲染
- 内存占用测试
- 渲染性能测试

**注意**: 文件较大（33MB），未提交到 git。可通过运行 `python create_test_pdfs.py` 重新生成。

---

## 重新生成测试文件

如果需要重新生成所有测试 PDF 文件（包括大文件），运行：

```bash
cd tests/fixtures
uv run python create_test_pdfs.py
```

## 测试用例建议

### 单元测试
```python
def test_parse_normal_pdf():
    """测试正常 PDF 解析"""
    parser = PDFParser()
    report = parser.parse("tests/fixtures/telecom_report_normal.pdf")
    assert report.source_type == "pdf"
    assert len(report.blocks) > 0
    assert "5G" in report.blocks[0].content

def test_parse_scanned_pdf():
    """测试扫描件 PDF 自动切换到渲染模式"""
    parser = PDFParser()
    report = parser.parse("tests/fixtures/telecom_report_scanned.pdf")
    assert report.source_type == "pdf"
    # 扫描件应该有渲染的图片
    assert len(report.images) > 0
    # blocks 应该是占位符
    assert "RENDERED" in report.blocks[0].ref

def test_parse_mixed_pdf():
    """测试混合 PDF（文本 + 图片）"""
    parser = PDFParser()
    report = parser.parse("tests/fixtures/telecom_report_mixed.pdf")
    assert len(report.blocks) > 0
    assert len(report.images) > 0

def test_parse_blank_pdf():
    """测试空白 PDF 边界情况"""
    parser = PDFParser()
    with pytest.raises(ValueError, match="未提取到任何文本内容"):
        parser.parse("tests/fixtures/blank.pdf")
```

### 集成测试
```python
@pytest.mark.asyncio
async def test_text_checker_on_pdf():
    """测试 TextChecker 在 PDF 上的运行"""
    parser = PDFParser()
    report = parser.parse("tests/fixtures/telecom_report_normal.pdf")

    checker = TextChecker(report, model_manager)
    result = checker.check({
        "keywords": ["5G", "network"],
        "match_mode": "any",
    })

    assert result.status == "passed"
```

## 文件大小说明

- 正常 PDF 和文本密集型 PDF 较小（< 20KB），已提交到 git
- 扫描件 PDF 较大（11-33MB），因为包含高分辨率图片
- 大文件未提交到 git，保持仓库体积小
- 可通过脚本随时重新生成

## 依赖

测试文件生成依赖：
- `pymupdf>=1.23.0` - PDF 创建和渲染
- `pillow>=10.0.0` - 图片处理
