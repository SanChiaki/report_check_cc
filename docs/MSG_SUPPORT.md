# MSG 邮件文件支持

## 功能概述

系统现已支持 `.msg` 格式的邮件文件检查。邮件内容可以在正文中，也可以在附件（PDF/Excel）中。

## 支持的文件类型

- `.msg` - Outlook 邮件文件
- 邮件附件：`.pdf`, `.xlsx`, `.xls`

## 解析能力

### 邮件元数据
- 主题 (subject)
- 发件人 (sender)
- 收件人 (to)
- 抄送 (cc)
- 发送日期 (date)
- 附件数量 (attachments_count)

### 内容解析
1. **邮件正文**：提取为文本内容块，位置标记为 `email_body`
2. **PDF 附件**：自动解析，位置标记为 `attachment:{文件名}:{原位置}`
3. **Excel 附件**：自动解析，位置标记为 `attachment:{文件名}:{原位置}`

## API 使用示例

### 上传邮件文件

```bash
curl -X POST "http://localhost:8000/api/v1/check/submit" \
  -F "files=@email_report.msg" \
  -F 'rules={
    "rules": [
      {
        "id": "r1",
        "name": "检查邮件正文包含关键词",
        "type": "text",
        "config": {
          "field": "email_body",
          "expected": "质检报告"
        }
      },
      {
        "id": "r2",
        "name": "检查附件中的数据",
        "type": "text",
        "config": {
          "field": "attachment:report.pdf:page_1",
          "expected": "合格"
        }
      }
    ]
  }'
```

### 规则配置示例

#### 1. 检查邮件正文
```json
{
  "id": "check_email_body",
  "name": "验证邮件正文内容",
  "type": "text",
  "config": {
    "field": "email_body",
    "expected": "报告已完成"
  }
}
```

#### 2. 检查 PDF 附件内容
```json
{
  "id": "check_pdf_attachment",
  "name": "验证 PDF 附件数据",
  "type": "text",
  "config": {
    "field": "attachment:report.pdf:page_1",
    "expected": "检验结果：合格"
  }
}
```

#### 3. 检查 Excel 附件内容
```json
{
  "id": "check_excel_attachment",
  "name": "验证 Excel 附件数据",
  "type": "text",
  "config": {
    "field": "attachment:data.xlsx:Sheet1!A1",
    "expected": "产品编号"
  }
}
```

#### 4. 多模态检查（整体分析）
```json
{
  "id": "multimodal_check",
  "name": "检查邮件整体结构",
  "type": "multimodal_check",
  "config": {
    "description": "验证邮件包含质检报告附件，且附件中每个质检项都有对应照片"
  }
}
```

## 实现细节

### 文件结构
```
src/report_check/parser/
├── msg.py          # MSG 解析器
├── pdf.py          # PDF 解析器（被 MSG 调用）
├── excel.py        # Excel 解析器（被 MSG 调用）
└── models.py       # 数据模型（新增 "email" 类型）
```

### 数据流
```
MSG 文件
  ↓
MSGParser.parse()
  ├─ 提取邮件元数据（主题、发件人等）
  ├─ 提取邮件正文 → ContentBlock(location="email_body")
  └─ 遍历附件
      ├─ PDF 附件 → PDFParser.parse()
      └─ Excel 附件 → ExcelParser.parse()
  ↓
合并所有内容为 ReportData
  ├─ source_type: "email"
  ├─ content_blocks: [正文块, 附件内容块...]
  └─ metadata: {subject, sender, to, date, ...}
```

### 位置标记规则
- 邮件正文：`email_body`
- PDF 附件：`attachment:report.pdf:page_1`
- Excel 附件：`attachment:data.xlsx:Sheet1!A1`

## 限制和注意事项

1. **文件大小限制**：单个文件最大 20MB
2. **附件类型**：仅支持 PDF 和 Excel 附件，其他类型会被跳过
3. **临时文件**：附件会临时保存到 `.temp_{邮件名}` 目录，解析完成后自动清理
4. **错误处理**：单个附件解析失败不会影响其他附件和邮件正文的解析

## 测试

运行 MSG 解析器测试：
```bash
uv run pytest tests/test_parser/test_msg.py -v
```

## 依赖

新增依赖：`extract-msg>=0.48.0`

安装：
```bash
uv sync
```
