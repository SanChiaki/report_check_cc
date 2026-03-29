# 报告一致性检查系统

AI 驱动的 Excel/PDF/MSG 报告一致性检查工具，支持文本、语义、图片、多模态、签名对比、API 和外部数据七种检查类型。

## 特性

- **多格式支持**：Excel (.xlsx/.xls)、PDF（含扫描件）和邮件 (.msg)
- **邮件智能解析**：自动提取邮件正文和附件（PDF/Excel）内容
- **多文件输入**：支持上传多个文件进行跨文件检查（如签名对比）
- **混合 PDF 解析**：自动检测正常 PDF 和扫描件，文本层缺失时自动切换为页面渲染
- **AI 驱动检查**：支持文本关键词、语义理解、图片内容识别、签名对比
- **网格编号法**：签名定位使用网格编号（如 C15-D15）而非像素坐标，精度提升 2 倍
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

- `/` — 提交检查：上传 Excel/PDF/MSG + 输入规则 DSL + 提交
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
    },
    {
      "id": "r4",
      "name": "质检项照片完整性",
      "type": "multimodal_check",
      "config": {
        "requirement": "检查报告中的每个质检项是否都有对应的现场照片证明",
        "context_hint": "质检项通常在'质检分类'下方列出"
      }
    },
    {
      "id": "r5",
      "name": "客户签名一致性",
      "type": "signature_compare",
      "config": {
        "file1_ref": 0,
        "file2_ref": 1,
        "signature_description": "客户手写签名",
        "grid_size": 20,
        "padding_cells": 1
      }
    },
    {
      "id": "r6",
      "name": "邮件正文包含关键词",
      "type": "text",
      "config": {
        "field": "email_body",
        "keywords": ["质检报告", "已完成"]
      }
    },
    {
      "id": "r7",
      "name": "邮件附件数据验证",
      "type": "text",
      "config": {
        "field": "attachment:report.pdf:page_1",
        "expected": "检验结果：合格"
      }
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
