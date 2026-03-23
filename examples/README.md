# PDF 报告检查使用示例

本文档展示如何使用 PDF 报告检查功能。

## 测试文件说明

### 1. 简单测试 PDF (`examples/test_report.pdf`)
包含基本的项目进度报告内容，适合快速测试。

### 2. 现有测试文件
- `tests/fixtures/telecom_report_normal.pdf` - 正常 PDF（包含可提取文本）
- `tests/fixtures/telecom_report_scanned.pdf` - 扫描件 PDF（纯图片）
- `tests/fixtures/multipage_scanned.pdf` - 多页扫描件
- `tests/fixtures/text_heavy.pdf` - 文本密集型 PDF

## 检测规则 DSL 示例

### 完整规则示例 (`examples/pdf_check_rules.json`)

```json
{
  "rules": [
    {
      "id": "pdf_text_001",
      "name": "检查报告标题",
      "type": "text",
      "enabled": true,
      "config": {
        "keywords": ["电信", "进度报告"],
        "match_mode": "all",
        "case_sensitive": false,
        "min_occurrences": 1
      }
    },
    {
      "id": "pdf_semantic_001",
      "name": "验证项目进度数据",
      "type": "semantic",
      "enabled": true,
      "config": {
        "content_description": "找到项目完成百分比相关的数字",
        "expected_value": "大于 50%",
        "check_prompt": "请判断找到的进度数据是否大于 50%"
      }
    },
    {
      "id": "pdf_image_001",
      "name": "检查是否包含图表",
      "type": "image",
      "enabled": true,
      "config": {
        "requirement": "图片中包含柱状图或折线图等数据可视化图表"
      }
    }
  ]
}
```

### 简化规则示例

#### 1. 纯文本检查
```json
{
  "rules": [
    {
      "id": "text_001",
      "name": "检查关键词",
      "type": "text",
      "config": {
        "keywords": ["项目", "进度"],
        "match_mode": "any"
      }
    }
  ]
}
```

#### 2. 语义检查
```json
{
  "rules": [
    {
      "id": "semantic_001",
      "name": "验证完成度",
      "type": "semantic",
      "config": {
        "content_description": "找到完成进度百分比",
        "expected_value": "75%",
        "check_prompt": "判断进度是否为 75%"
      }
    }
  ]
}
```

#### 3. 图片检查（适用于扫描件）
```json
{
  "rules": [
    {
      "id": "image_001",
      "name": "检查图表存在性",
      "type": "image",
      "config": {
        "requirement": "包含数据图表"
      }
    }
  ]
}
```

## API 调用示例

### 使用 curl 提交检查任务

```bash
# 1. 提交 PDF 检查任务
curl -X POST http://localhost:8000/api/v1/check/submit \
  -F "file=@examples/test_report.pdf" \
  -F "rules=$(cat examples/pdf_check_rules.json)"

# 响应示例:
# {
#   "task_id": "abc-123-def",
#   "status": "pending",
#   "message": "任务已提交"
# }

# 2. 查询检查结果
curl http://localhost:8000/api/v1/check/result/abc-123-def

# 响应示例:
# {
#   "task_id": "abc-123-def",
#   "status": "completed",
#   "file_name": "test_report.pdf",
#   "results": [
#     {
#       "rule_id": "pdf_text_001",
#       "rule_name": "检查报告标题",
#       "status": "passed",
#       "message": "Found 2 occurrence(s) of keywords: 电信, 进度报告",
#       "location": {"page": 1, "location": "page_1"}
#     }
#   ]
# }
```

### 使用 Python 调用

```python
import requests
import json

# 提交检查任务
with open('examples/test_report.pdf', 'rb') as f:
    with open('examples/pdf_check_rules.json', 'r') as r:
        response = requests.post(
            'http://localhost:8000/api/v1/check/submit',
            files={'file': f},
            data={'rules': r.read()}
        )

task_id = response.json()['task_id']
print(f"任务 ID: {task_id}")

# 查询结果
import time
while True:
    result = requests.get(f'http://localhost:8000/api/v1/check/result/{task_id}')
    data = result.json()

    if data['status'] == 'completed':
        print("检查完成！")
        for item in data['results']:
            print(f"- {item['rule_name']}: {item['status']}")
        break
    elif data['status'] == 'failed':
        print(f"检查失败: {data.get('error')}")
        break

    time.sleep(2)
```

## 规则类型详解

### 1. Text（文本检查）
适用于：正常 PDF（可提取文本）

```json
{
  "type": "text",
  "config": {
    "keywords": ["关键词1", "关键词2"],
    "match_mode": "any|all|exact",
    "case_sensitive": false,
    "min_occurrences": 1
  }
}
```

### 2. Semantic（语义检查）
适用于：正常 PDF 和扫描件 PDF（通过 AI 理解）

```json
{
  "type": "semantic",
  "config": {
    "content_description": "描述要查找的内容",
    "expected_value": "期望值",
    "check_prompt": "AI 判断提示词"
  }
}
```

### 3. Image（图片检查）
适用于：包含图片的 PDF 和扫描件 PDF

```json
{
  "type": "image",
  "config": {
    "requirement": "图片要求描述",
    "image_filter": {
      "keywords": ["可选的过滤关键词"]
    }
  }
}
```

### 4. API（API 验证）
适用于：所有 PDF 类型

```json
{
  "type": "api",
  "config": {
    "content_description": "要提取的内容",
    "api_url": "https://api.example.com/validate",
    "method": "POST",
    "validation": {
      "operator": "equals|contains|gt|lt",
      "expected": "期望值"
    }
  }
}
```

### 5. External Data（外部数据对比）
适用于：所有 PDF 类型

```json
{
  "type": "external_data",
  "config": {
    "content_description": "要对比的内容",
    "external_data_source": {
      "type": "api",
      "url": "https://api.example.com/data"
    },
    "comparison_prompt": "对比提示词"
  }
}
```

## 注意事项

### PDF 类型自动检测
系统会自动检测 PDF 类型：
- **正常 PDF**：每页文本 ≥ 50 字符 → 使用文本提取
- **扫描件 PDF**：每页文本 < 50 字符 → 渲染为图片（150 DPI）

### 检查类型适用性
| 检查类型 | 正常 PDF | 扫描件 PDF |
|---------|---------|-----------|
| Text    | ✅ 高效  | ❌ 不适用  |
| Semantic| ✅ 推荐  | ✅ 推荐    |
| Image   | ✅ 适用  | ✅ 适用    |
| API     | ✅ 适用  | ✅ 适用    |
| External| ✅ 适用  | ✅ 适用    |

### 性能建议
- 扫描件 PDF 处理较慢（需要渲染页面）
- 大文件建议限制在 20MB 以内
- 多页扫描件建议使用语义检查而非逐页图片检查

## 快速开始

```bash
# 1. 启动后端服务
uv run uvicorn report_check.main:app --reload

# 2. 创建测试 PDF
uv run python examples/create_test_pdf.py

# 3. 提交检查任务
curl -X POST http://localhost:8000/api/v1/check/submit \
  -F "file=@examples/test_report.pdf" \
  -F 'rules={"rules":[{"id":"t1","name":"测试","type":"text","config":{"keywords":["电信"],"match_mode":"any"}}]}'

# 4. 查看结果（替换 task_id）
curl http://localhost:8000/api/v1/check/result/{task_id}
```
