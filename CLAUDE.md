## 项目概述

AI 驱动的 Excel/PDF/MSG 报告一致性检查系统。用户上传一个或多个报告文件和规则 DSL，后端异步解析文件、执行规则、持久化结果，前端轮询展示检查进度与结果。

当前支持 8 种检查类型：`text`、`semantic`、`image`、`multimodal_check`、`image_consistency`、`signature_compare`、`api`、`external_data`。

邮件 `.msg` 是一等输入格式：系统会同时解析邮件正文和附件（PDF/Excel），并把附件内容映射到统一的 `ReportData` 结构里。

## 常用命令

### 后端

```bash
uv sync
uv run uvicorn report_check.main:app --reload
uv run pytest
uv run pytest tests/test_api/test_router.py
uv run pytest tests/test_api/test_router.py::test_function_name
```

### 前端

```bash
cd frontend && npm install
cd frontend && npm run dev
cd frontend && npm run build
```

### Docker

```bash
cp .env.example .env
docker compose up -d
docker compose logs -f app
docker compose down
```

## 代码结构与架构

### 1. 应用入口与运行时装配

`src/report_check/main.py` 在 FastAPI 生命周期里完成整套运行时装配：
- 读取 `config/models.yaml` 和 `config/app.yaml`
- 初始化 `Database`、`FileStorage`、`TaskQueue`、`ArtifactsManager`
- 构建 `ModelManager` 并注册各 provider adapter
- 启动 `BackgroundWorker`

这意味着多数后端行为不是请求内同步完成，而是“API 接收任务 + Worker 异步消费任务”。

### 2. API 层只负责校验、入库、入队

`src/report_check/api/router.py` 负责：
- 校验上传文件类型和大小（Excel/PDF/MSG，20MB 上限）
- 解析规则 DSL / `context_vars`
- 保存主文件和额外文件
- 创建任务并写入 SQLite
- 将 `task_id` 放入内存队列
- 提供结果查询、模板查询、artifacts 浏览/下载接口

关键点：`/api/v1/check/submit` 只提交任务，不直接执行检查；前端通过 `/api/v1/check/result/{task_id}` 轮询结果。

### 3. Worker 是核心业务编排层

`src/report_check/worker/worker.py` 是后端主流程核心，顺序大致是：
1. 从 `TaskQueue` 取任务
2. 根据文件类型选择 `ExcelParser` / `PDFParser` / `MSGParser`
3. 对扫描 PDF 按需触发视觉 OCR，把识别文本补回 `report_data`
4. 通过 `RuleEngine` 合并规则，并用 `VariableResolver` 解析 `${task_id}` 之类变量
5. 用 `CheckerFactory` 为每条规则创建 checker
6. 执行检查，收集 `CheckResult`
7. 写入数据库并保存 artifacts

另外这里还承担了几个系统级策略：
- 启动时恢复 orphaned `processing` 任务
- API / external_data 规则的简单熔断（同一 API 连续失败 3 次后跳过）
- 任务级过程文件落盘

### 4. 统一数据通路：先解析为 ReportData，再交给 checker

解析器位于 `src/report_check/parser/`：
- `excel.py`：解析工作表内容和嵌入图片
- `pdf.py`：普通 PDF 走文本/图片提取，扫描件可走页面渲染与视觉 OCR
- `msg.py`：提取邮件元数据、正文和附件内容
- `renderer.py`：把报告渲染成页面图片，供多模态类 checker 使用

核心思路是把不同输入格式统一为 `ReportData`，这样 checker 不直接关心原始文件格式，而是消费统一的内容块与图片集合。

### 5. Checker 体系是扩展点

所有 checker 都继承 `BaseChecker`，并通过 `CheckerFactory` 注册和创建。当前映射在 `src/report_check/checkers/factory.py`。

现有 checker 分工：
- `text`：关键词/字段级文本匹配
- `semantic`：文本语义理解
- `image`：单图内容是否满足要求
- `multimodal_check`：基于整页渲染图理解报告结构与图文关系
- `image_consistency`：检查项描述与配图是否一致
- `signature_compare`：跨文件签名定位、裁切、比对
- `api` / `external_data`：调用外部接口校验报告内容

新增检查类型时，按当前约定应：
1. 新建 checker 并继承 `BaseChecker`
2. 实现 `check(rule_config)`
3. 在 `CheckerFactory` 注册
4. 如有新增 DSL 类型，同步更新规则校验逻辑

### 6. 规则系统分为三层

规则相关逻辑在 `src/report_check/engine/`：
- `validator.py`：校验 DSL 基本结构与 rule type 合法性
- `rule_engine.py`：合并基础规则和用户规则，并过滤 `enabled: false`
- `variable_resolver.py`：解析规则配置中的变量引用

规则 DSL 顶层格式：

```json
{
  "rules": [
    {
      "id": "r1",
      "name": "...",
      "type": "text|semantic|image|multimodal_check|image_consistency|signature_compare|api|external_data",
      "config": {}
    }
  ]
}
```

### 7. 模型调用统一走 ModelManager

不要在业务代码里直接调用 OpenAI/Qwen SDK。统一通过 `src/report_check/models/manager.py` 暴露的：
- `call_text_model()`
- `call_multimodal_model()`

`ModelManager` 负责按 provider 查找 adapter，并做带退避的重试。当前运行时默认注册的是 `OpenAIAdapter`，但配置层已经按“provider + adapter”模式组织，可以继续扩展。

### 8. 存储分两类：任务状态 + 过程证据

- `src/report_check/storage/database.py`：SQLite，保存任务、结果、规则模板
- `src/report_check/storage/artifacts.py`：把任务执行过程保存到 `data/tasks/{task_id}/`

artifacts 目录按阶段划分：
- `0_upload/` 原始上传文件
- `1_parsed/` 解析结果和抽取图片
- `2_rules/` 用户规则、合并后规则、变量解析后规则
- `3_checks/` 每条规则的执行细节
- `4_ai_calls/` AI 请求/响应记录
- `5_result/` 最终结果与汇总

如果要排查“模型为什么这么判”“定位是否错了”，优先看 artifacts，而不是只看接口返回值。

### 9. 前端是轻量三页应用

`frontend/src/router/index.ts` 当前只有 3 个页面：
- `/`：`CheckPage.vue`，上传文件、选择模板、编辑规则并提交任务
- `/result/:taskId`：`ResultPage.vue`，轮询任务状态并展示结果
- `/rules`：`RuleConfig.vue`，规则可视化编辑

前端本身业务较薄，主要职责是把规则 DSL 与文件上传给后端，并把异步任务状态可视化。

## 重要约定

1. 新增 checker 时，优先复用 `ReportData`、`BaseChecker`、`ModelManager` 这条主链路，不要绕开工厂和模型管理层。
2. 需要 AI 定位内容时，优先使用 `BaseChecker.locate_content(...)` 的既有机制，不要在各 checker 内重复实现定位流程。
3. checker 内部发生异常时，应返回 `CheckResult(status="error", ...)`，不要把异常直接抛到 worker 顶层。
4. 新增 rule type 时，除了注册 checker，还要同步更新 API 校验中的合法类型列表。
5. 与任务排查相关的问题，先看 `data/tasks/{task_id}/` 下的 artifacts，再决定是否需要加日志。

## 配置与环境变量

模型配置在 `config/models.yaml`，应用配置在 `config/app.yaml`。

常见环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `OPENAI_API_BASE_URL` | OpenAI API 基础 URL | - |
| `QWEN_API_KEY` | Qwen API Key | - |
| `QWEN_API_BASE_URL` | Qwen API 基础 URL | - |
| `MODEL_PROVIDER` | 默认模型提供商 | `openai` |

`config/app.yaml` 当前还定义了这些关键运行参数：
- SQLite 路径：`data/reports.db`
- 上传目录：`data/uploads`
- 默认限流：`10/minute`
- 文件大小/单元格/图片数量限制

## 开发注意事项

**关闭开发服务器：**
- `uv run uvicorn` 启动链路是 `uv run → python .venv/bin/uvicorn`
- `pkill -f "uvicorn"` 只会杀掉 `uv run` 父进程，子进程可能继续存活
- 正确做法是先 `ps aux | grep uvicorn` 确认 PID，再逐个清理并确认无残留后重启
