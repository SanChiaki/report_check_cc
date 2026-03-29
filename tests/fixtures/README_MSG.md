# 测试 MSG 文件说明

## 测试文件位置

由于 MSG 是 Microsoft Outlook 专有格式，需要手动创建测试文件。

### 方法 1：使用 Outlook 创建（推荐）

1. 打开 Microsoft Outlook
2. 创建新邮件，填写以下内容：
   ```
   主题: 测试质检报告
   发件人: test@example.com
   收件人: receiver@example.com
   正文:
   这是一封测试邮件，用于验证报告检查系统。

   质检报告已完成，所有检查项均已通过。
   详细数据请查看附件。
   ```
3. 添加附件（可选）：
   - 添加一个 PDF 文件（如 report.pdf）
   - 或添加一个 Excel 文件（如 data.xlsx）
4. 点击"文件" → "另存为" → 选择格式 "Outlook 邮件格式 (*.msg)"
5. 保存到：`tests/fixtures/test_email.msg`

### 方法 2：从邮箱导出

1. 在 Outlook 中打开任意邮件
2. 拖拽邮件到桌面或文件夹
3. 重命名为 `test_email.msg`
4. 移动到 `tests/fixtures/` 目录

### 方法 3：使用在线 MSG 文件

可以从以下来源获取测试 MSG 文件：
- https://github.com/mattgwwalker/msg-extractor/tree/master/tests/test_data
- 任何包含 MSG 测试文件的开源项目

## 测试 API

### 使用 curl 测试

```bash
# 1. 启动服务
uv run uvicorn report_check.main:app --reload

# 2. 提交 MSG 文件检查
curl -X POST "http://localhost:8000/api/v1/check/submit" \
  -F "files=@tests/fixtures/test_email.msg" \
  -F 'rules={
    "rules": [
      {
        "id": "r1",
        "name": "检查邮件正文包含关键词",
        "type": "text",
        "config": {
          "field": "email_body",
          "keywords": ["质检报告", "完成"]
        }
      }
    ]
  }'

# 3. 查询结果（替换 {task_id} 为返回的任务 ID）
curl "http://localhost:8000/api/v1/check/result/{task_id}"
```

### 使用 Python 测试

```python
import requests

# 提交检查
with open("tests/fixtures/test_email.msg", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/check/submit",
        files={"files": ("test.msg", f, "application/vnd.ms-outlook")},
        data={
            "rules": '''{
                "rules": [
                    {
                        "id": "r1",
                        "name": "检查邮件正文",
                        "type": "text",
                        "config": {"field": "email_body", "keywords": ["测试"]}
                    }
                ]
            }'''
        }
    )

task_id = response.json()["task_id"]
print(f"任务 ID: {task_id}")

# 查询结果
import time
time.sleep(2)
result = requests.get(f"http://localhost:8000/api/v1/check/result/{task_id}")
print(result.json())
```

## 规则示例

### 检查邮件正文
```json
{
  "id": "check_body",
  "name": "验证邮件正文内容",
  "type": "text",
  "config": {
    "field": "email_body",
    "keywords": ["质检报告", "完成", "通过"]
  }
}
```

### 检查邮件附件（PDF）
```json
{
  "id": "check_pdf_attachment",
  "name": "验证 PDF 附件内容",
  "type": "text",
  "config": {
    "field": "attachment:report.pdf:page_1",
    "expected": "检验结果：合格"
  }
}
```

### 检查邮件附件（Excel）
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

### 多模态检查
```json
{
  "id": "multimodal_check",
  "name": "整体验证邮件结构",
  "type": "multimodal_check",
  "config": {
    "requirement": "邮件应包含质检报告说明，且附件中包含详细数据"
  }
}
```

## 预期解析结果

成功解析后，MSG 文件会被转换为以下结构：

```json
{
  "file_name": "test_email.msg",
  "source_type": "email",
  "metadata": {
    "subject": "测试质检报告",
    "sender": "test@example.com",
    "to": "receiver@example.com",
    "date": "2024-01-15 10:00:00",
    "cc": "",
    "attachments_count": 2
  },
  "content_blocks": [
    {
      "content": "这是一封测试邮件...",
      "location": "email_body",
      "content_type": "text"
    },
    {
      "content": "PDF 附件内容...",
      "location": "attachment:report.pdf:page_1",
      "content_type": "text"
    }
  ],
  "images": [...]
}
```

## 注意事项

1. MSG 文件必须是有效的 Outlook 邮件格式
2. 文件大小限制：20MB
3. 支持的附件类型：PDF、Excel（.xlsx/.xls）
4. 其他类型附件会被跳过
5. 附件解析失败不影响邮件正文和其他附件
