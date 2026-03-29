# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

AI 驱动的 Excel/PDF 报告一致性检查系统，支持七种检查类型：文本、语义、图片、多模态、签名对比、API 和外部数据验证。

## 开发命令

**后端开发：**
```bash
uv sync                                    # 安装依赖
uv run uvicorn report_check.main:app --reload  # 启动开发服务器 (http://localhost:8000)
uv run pytest                              # 运行全部测试
uv run pytest tests/test_specific.py       # 运行单个测试文件
uv run pytest tests/test_specific.py::test_function_name  # 运行单个测试函数
```

**前端开发：**
```bash
cd frontend && npm install                 # 安装依赖
cd frontend && npm run dev                 # 启动开发服务器 (http://localhost:5173)
```

**Docker 部署（仅后端）：**
```bash
cp .env.example .env                       # 配置环境变量（必须包含 OPENAI_API_BASE_URL）
docker compose up -d                       # 后台启动后端服务
docker compose logs -f app                 # 查看后端日志
docker compose down                        # 停止服务
```

**前端独立部署：**
```bash
cd frontend
npm install
npm run build                              # 构建生产版本到 dist/
# 将 dist/ 目录部署到 Nginx、CDN 或其他静态托管服务
```

**注意事项：**
- Docker 仅包含后端服务（端口 8000）
- 前端需要独立部署，通过环境变量或构建时配置指向后端 API 地址
- 后端已配置 CORS，支持跨域访问
- 本地开发时前端使用 Vite 代理（`npm run dev`），生产环境直接请求后端

## 架构设计

### 核心组件

1. **CheckerFactory + BaseChecker 模式**
   - 所有检查器继承 `BaseChecker` (src/report_check/checkers/base.py)
   - 通过 `CheckerFactory.create(type, ...)` 创建检查器实例
   - 七种检查器：TextChecker, SemanticChecker, ImageChecker, MultimodalChecker, SignatureChecker, ApiChecker, ExternalDataChecker
   - 每个检查器返回 `CheckResult` 数据类

2. **异步任务队列架构**
   - `TaskQueue` (worker/queue.py): 内存队列，使用 asyncio.Queue
   - `BackgroundWorker` (worker/worker.py): 后台工作进程，启动时自动恢复孤儿任务
   - `Database` (storage/database.py): SQLite 存储，跟踪任务状态 (pending/processing/completed/failed)
   - 任务提交流程：API → 创建任务 → 入队 → Worker 处理 → 更新结果

3. **规则引擎**
   - `RuleEngine` (engine/rule_engine.py): 合并基础规则和用户规则，过滤禁用规则
   - `VariableResolver` (engine/variable_resolver.py): 解析规则配置中的变量引用 (如 `${task_id}`)
   - 规则 DSL 格式：`{"rules": [{"id": "r1", "name": "...", "type": "text|semantic|image|multimodal_check|signature_compare|api|external_data", "config": {...}}]}`

4. **AI 模型管理**
   - `ModelManager` (models/manager.py): 统一接口，支持多提供商
   - `OpenAIAdapter`: 适配器模式，支持分别配置文本模型和多模态模型的 base_url
   - 配置文件：config/models.yaml，支持环境变量替换

5. **PDF 解析**
   - `PDFParser` (parser/pdf.py): 混合解析方案
   - 正常 PDF：使用 pdfplumber 提取文本和嵌入图片
   - 扫描件 PDF：使用 PyMuPDF 渲染页面为图片（无文字层时自动切换）
   - 图片压缩：`parser/utils.py` 限制 2048x2048 像素，2MB 大小

6. **报告渲染 (ReportRenderer)**
   - `ReportRenderer` (parser/renderer.py): 将报告转换为图片供多模态分析
   - Excel：使用 PIL 将工作表内容渲染为图片
   - PDF：使用 PyMuPDF 渲染页面为图片
   - 支持已解析的页面图片复用

7. **多模态检查 (MultimodalChecker)**
   - `MultimodalChecker` (checkers/multimodal.py): 整体分析报告结构（文本+图片）
   - 使用多模态 AI 理解动态内容（如质检项列表）
   - 适用于：质检报告（检查每个质检项是否有对应照片）、结构化列表验证
   - 自动渲染报告为图片后调用多模态模型分析

8. **签名对比检查 (SignatureChecker)**
   - `SignatureChecker` (checkers/signature.py): 跨文件签名对比，验证是否同一人签名
   - 网格编号法：将图片划分为 NxN 网格（默认 20x20），AI 返回边界格子（如 C15-D15）而非像素坐标
   - 边界格子定位：AI 返回 top_left_cell 和 bottom_right_cell，相比像素坐标精度提升 2 倍
   - 可配置 padding：支持向外扩展 N 个格子（默认 1）确保完整覆盖签名
   - 网格可视化：红色列标签（A-T）、蓝色行标签（1-20）、灰色网格线，保存为 artifacts 便于调试
   - 签名裁切：基于 AI 返回的格子范围裁切签名图片，保存为证据
   - 多模态对比：将两张裁切后的签名图发送给 AI 判断是否同一人
   - 适用于：合同签名验证、报告签名一致性检查

9. **容错机制**
   - 孤儿任务恢复：启动时自动重新入队未完成的 processing 任务
   - API 熔断器：同一 API 连续失败 3 次后跳过后续调用
   - AI 调用重试：locate_content 方法最多重试 3 次

10. **过程文件管理 (Artifacts)**
   - `ArtifactsManager` (storage/artifacts.py): 管理任务过程文件的保存和查询
   - 每个任务拥有独立文件夹：`data/tasks/{task_id}/`
   - 目录结构：
     - `0_upload/`: 原始上传文件
     - `1_parsed/`: 解析后的数据（包括提取的图片和页面）
     - `2_rules/`: 规则配置（用户规则、合并后规则、解析后规则）
     - `3_checks/`: 每个检查规则的详细执行记录
     - `4_ai_calls/`: AI 调用的请求和响应记录
     - `5_result/`: 最终结果
   - API 接口：
     - `GET /api/v1/tasks/{task_id}/artifacts` - 列出任务的所有过程文件
     - `GET /api/v1/tasks/{task_id}/artifacts/download` - 下载所有过程文件为 zip
     - `GET /api/v1/tasks/{task_id}/artifacts/{file_path}` - 获取单个文件

### 数据流

```
用户上传 Excel/PDF + 规则 DSL
  ↓
FastAPI 接收 (api/router.py)
  ↓
创建任务并入队 (worker/queue.py)
  ↓
BackgroundWorker 处理 (worker/worker.py)
  ├─ ExcelParser/PDFParser 解析文件 (parser/)
  ├─ RuleEngine 合并规则 (engine/rule_engine.py)
  ├─ VariableResolver 解析变量 (engine/variable_resolver.py)
  ├─ CheckerFactory 创建检查器 (checkers/factory.py)
  └─ 执行检查并保存结果 (storage/database.py)
  ↓
前端轮询获取结果 (/api/v1/check/result/{task_id})
```

## 重要约定

1. **检查器开发**：新增检查器需继承 `BaseChecker`，实现 `check(rule_config)` 方法，并在 `CheckerFactory` 注册
2. **AI 调用**：使用 `model_manager.call_text_model()` 或 `call_multimodal_model()`，不要直接调用 OpenAI/Qwen API
3. **位置定位**：使用 `BaseChecker.locate_content(description)` 让 AI 在报告中定位内容
4. **错误处理**：检查器异常应返回 `CheckResult(status="error", message="...")`，不要抛出异常
5. **配置管理**：环境变量通过 config/models.yaml 和 .env 管理，使用 `${VAR_NAME}` 语法

## 模型配置

支持分别配置文本模型和多模态模型的 base_url：

```yaml
providers:
  openai:
    api_key: ${OPENAI_API_KEY}
    text_model: gpt-4o
    text_base_url: ${TEXT_API_URL}        # 文本模型专属
    multimodal_model: gpt-4o
    multimodal_base_url: ${VISION_API_URL}  # 多模态模型专属
```

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_API_BASE_URL` | OpenAI API 基础 URL | - |
| `QWEN_API_KEY` | Qwen API Key | - |
| `QWEN_API_BASE_URL` | Qwen API 基础 URL | - |
| `MODEL_PROVIDER` | 默认模型提供商 | `openai` |
