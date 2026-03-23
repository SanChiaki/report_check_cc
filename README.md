# 报告一致性检查系统

AI 驱动的 Excel/PDF 报告一致性检查工具，支持文本、语义、图片、API 和外部数据五种检查类型。

## 特性

- **多格式支持**：Excel (.xlsx/.xls) 和 PDF（含扫描件）
- **混合 PDF 解析**：自动检测正常 PDF 和扫描件，文本层缺失时自动切换为页面渲染
- **AI 驱动检查**：支持文本关键词、语义理解、图片内容识别
- **灵活规则**：通过 DSL 配置检查规则，支持变量替换

## 快速开始

### 本地开发

**后端：**

```bash
uv sync
uv run uvicorn report_check.main:app --reload
# API: http://localhost:8000
```

**前端：**

```bash
cd frontend
npm install
npm run dev
# 前端: http://localhost:5173
```

### Docker 部署

```bash
cp .env.example .env  # 填写 API Key
docker compose up
# 后端: http://localhost:8000
# 前端: http://localhost:5173
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_API_BASE_URL` | OpenAI API 基础 URL | - |
| `QWEN_API_KEY` | Qwen API Key | - |
| `QWEN_API_BASE_URL` | Qwen API 基础 URL | - |
| `MODEL_PROVIDER` | 模型提供商 (`openai` / `qwen`) | `openai` |

## 模型配置

支持分别配置文本模型和多模态模型的 API 端点：

```yaml
# config/models.yaml
providers:
  openai:
    api_key: ${OPENAI_API_KEY}
    text_model: gpt-4o
    text_base_url: ${TEXT_API_URL}        # 文本模型端点
    multimodal_model: qwen-vl-plus
    multimodal_base_url: ${VISION_API_URL}  # 多模态模型端点
```

## 前端页面

- `/` — 提交检查：上传 Excel/PDF + 输入规则 DSL + 提交
- `/result/:taskId` — 查看检查结果（自动轮询）
- `/rules` — 规则配置：可视化编辑规则 DSL

## 规则 DSL 示例

```json
{
  "rules": [
    {
      "id": "r1",
      "name": "检查交付内容章节",
      "type": "text",
      "config": { "keywords": ["交付内容"], "match_mode": "any" }
    },
    {
      "id": "r2",
      "name": "移交记录完整性",
      "type": "semantic",
      "config": { "requirement": "移交记录中要包含移交人、移交时间、移交命令" }
    },
    {
      "id": "r3",
      "name": "机房清理图片",
      "type": "image",
      "config": { "requirement": "清理机房，图片应显示干净整洁的机房环境" }
    }
  ]
}
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/check/submit` | 提交检查任务 |
| `GET` | `/api/v1/check/result/{task_id}` | 查询检查结果 |
| `POST` | `/api/v1/rules/validate` | 验证规则 DSL |
| `GET` | `/api/v1/templates` | 获取规则模板列表 |
| `GET` | `/api/v1/health` | 健康检查 |
