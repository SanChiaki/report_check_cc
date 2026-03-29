# MSG 邮件支持功能实现总结

## 实现内容

### 1. 核心功能
- ✅ 新增 `MSGParser` 解析器 (src/report_check/parser/msg.py)
- ✅ 支持邮件正文提取（主题、发件人、收件人、日期、正文内容）
- ✅ 自动解析 PDF 和 Excel 附件
- ✅ 统一输出为 `ReportData` 格式

### 2. API 更新
- ✅ 支持 `.msg` 文件上传 (api/router.py)
- ✅ 添加 MSG 文件 magic number 验证 (`\xD0\xCF\x11\xE0`)
- ✅ 更新文件类型 MIME type 支持

### 3. Worker 集成
- ✅ BackgroundWorker 支持 MSG 文件解析 (worker/worker.py)
- ✅ 主文件和额外文件均支持 MSG 格式

### 4. 数据模型
- ✅ ReportData.source_type 新增 "email" 类型 (parser/models.py)
- ✅ 位置标记规则：
  - 邮件正文：`email_body`
  - 附件内容：`attachment:{文件名}:{原位置}`

### 5. 依赖管理
- ✅ 添加 `extract-msg>=0.48.0` 依赖 (pyproject.toml)
- ✅ 已通过 `uv sync` 安装

### 6. 测试
- ✅ 单元测试：tests/test_parser/test_msg.py (3 个测试用例)
  - 邮件正文解析
  - PDF 附件解析
  - Excel 附件解析
- ✅ API 集成测试：tests/test_api/test_msg_api.py (3 个测试用例)
- ✅ 所有测试通过

### 7. 文档
- ✅ 更新 CLAUDE.md（项目架构说明）
- ✅ 更新 README.md（功能特性和示例）
- ✅ 新增 docs/MSG_SUPPORT.md（详细使用文档）

## 文件变更清单

### 新增文件
```
src/report_check/parser/msg.py          # MSG 解析器
tests/test_parser/test_msg.py           # 单元测试
tests/test_api/test_msg_api.py          # API 测试
docs/MSG_SUPPORT.md                     # 使用文档
```

### 修改文件
```
pyproject.toml                          # 添加 extract-msg 依赖
src/report_check/parser/models.py       # 添加 "email" 类型
src/report_check/api/router.py          # 支持 .msg 上传和验证
src/report_check/worker/worker.py       # 集成 MSGParser
CLAUDE.md                               # 更新架构说明
README.md                               # 更新功能说明
```

## 使用示例

### 上传邮件文件
```bash
curl -X POST "http://localhost:8000/api/v1/check/submit" \
  -F "files=@email_report.msg" \
  -F 'rules={
    "rules": [
      {
        "id": "r1",
        "name": "检查邮件正文",
        "type": "text",
        "config": {"field": "email_body", "expected": "质检报告"}
      },
      {
        "id": "r2",
        "name": "检查附件数据",
        "type": "text",
        "config": {"field": "attachment:report.pdf:page_1", "expected": "合格"}
      }
    ]
  }'
```

### 规则配置
```json
{
  "rules": [
    {
      "id": "check_email_body",
      "name": "验证邮件正文",
      "type": "text",
      "config": {"field": "email_body", "keywords": ["报告", "完成"]}
    },
    {
      "id": "check_attachment",
      "name": "验证附件内容",
      "type": "semantic",
      "config": {
        "field": "attachment:data.xlsx:Sheet1",
        "requirement": "包含产品编号和检验结果"
      }
    }
  ]
}
```

## 技术细节

### 解析流程
1. 使用 `extract_msg` 库打开 MSG 文件
2. 提取邮件元数据（主题、发件人等）
3. 提取邮件正文为 ContentBlock
4. 遍历附件：
   - 保存到临时目录
   - 根据扩展名调用对应解析器（PDFParser/ExcelParser）
   - 合并解析结果
   - 清理临时文件
5. 返回统一的 ReportData 对象

### 位置标记
- 邮件正文：`location="email_body"`
- PDF 附件：`location="attachment:report.pdf:page_1"`
- Excel 附件：`location="attachment:data.xlsx:Sheet1!A1"`

### 错误处理
- 单个附件解析失败不影响其他附件
- 不支持的附件类型会被跳过并记录警告
- 临时文件在 finally 块中确保清理

## 测试结果

```bash
$ uv run pytest tests/test_parser/test_msg.py -v
======================== 3 passed, 5 warnings in 0.11s ========================

$ uv run pytest tests/test_api/test_router.py -v
======================== 10 passed, 5 warnings in 0.53s ========================
```

## 后续优化建议

1. **性能优化**：大附件并行解析
2. **格式支持**：添加 .eml 格式支持
3. **附件类型**：支持更多附件格式（Word、图片等）
4. **邮件内容**：支持 HTML 邮件正文解析
5. **批量处理**：支持批量邮件文件检查

## 兼容性

- Python 3.11+
- 向后兼容：不影响现有 Excel/PDF 功能
- 依赖稳定：extract-msg 是成熟的邮件解析库
