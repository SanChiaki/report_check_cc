# 报告一致性检查系统 - 设计文档

## 1. 概述

### 1.1 背景

当前交付报告的一致性检查依赖服务经理人工审核，存在效率低、反复打回的问题。本系统通过 AI 自动化检查 Excel 报告，减少人工审核次数。

### 1.2 核心目标

- 支持 5 种检查类型：文本检查、语义检查、图片检查、API 检查、外部数据检查
- 语义化规则 DSL，不依赖固定的报告模板结构
- 支持多种 AI 模型切换（OpenAI / Qwen），区分文本模型和多模态模型
- 异步任务处理，支持排队
- 检查结果精确到单元格定位，并提供修改建议和示例

### 1.3 约束条件

- **报告格式**：Excel 文件，通常单个工作表，结构不固定（模板自由）
- **图片规模**：每份报告 1-5 张图片，图片检查规则 1-3 条
- **报告类型**：10-20 种，有不同的业务流程
- **并发量**：1-5 个报告同时处理，需快速响应（30 秒内），支持横向扩展
- **规则配置者**：技术人员和业务人员共用同一套 DSL，前端提供可视化配置
- **外部 API**：已存在，有明确接口文档，只需调用
- **AI 模型**：开发阶段使用 OpenAI，生产环境使用内部部署的 Qwen

### 1.4 技术栈

- 后端：Python、FastAPI、Pydantic
- Excel 处理：openpyxl、Pillow
- AI 调用：openai SDK、自定义 Qwen 适配器
- 数据存储：SQLite
- 开发环境：uv 虚拟环境管理
- 部署：Docker 容器
- 前端：Vue（以演示检测效果、配置规则为主）

---

## 2. 系统架构

### 2.1 核心组件

```
┌──────────────────────────────────────────────────────────────┐
│                        API 层 (FastAPI)                       │
│  POST /api/v1/check/submit    GET /api/v1/check/result/{id}  │
│  GET /api/v1/templates        GET /api/v1/templates/{id}      │
└──────────────┬───────────────────────────────┬────────────────┘
               │                               │
               ▼                               ▼
┌──────────────────────┐        ┌──────────────────────────────┐
│    任务管理器         │        │       数据存储 (SQLite)       │
│    TaskQueue          │        │  tasks / check_results /     │
│    BackgroundWorker   │        │  rule_templates              │
└──────────┬───────────┘        └──────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│                      规则引擎 (RuleEngine)                    │
│              规则解析 → 规则验证 → 规则执行协调                 │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────┐
│                    检查器层 (Checkers)                         │
│  TextChecker │ SemanticChecker │ ImageChecker │ ApiChecker    │
│              │                 │              │ ExternalData  │
└──────────┬───────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────┐  ┌────────────────────────────────┐
│  Excel 解析器            │  │   AI 模型抽象层                 │
│  ExcelParser             │  │   ModelManager                 │
│  ReportSummarizer        │  │   OpenAIAdapter / QwenAdapter  │
└─────────────────────────┘  └────────────────────────────────┘
```

### 2.2 数据流

```
用户上传 Excel + 规则 DSL
        │
        ▼
  API 接收 → 创建任务 → 返回 task_id
                │
                ▼
          任务队列（排队）
                │
                ▼
  后台工作进程取出任务
        │
        ▼
  Excel 解析器提取所有内容
        │
        ▼
  规则引擎加载规则，逐条执行
        │
        ├── TextChecker：全文搜索关键词
        ├── SemanticChecker：AI 定位 + 语义验证
        ├── ImageChecker：AI 分析图片内容
        ├── ApiChecker：AI 定位提取内容 → 调用外部 API
        └── ExternalDataChecker：AI 定位 + 外部 API + AI 分析
        │
        ▼
  结果聚合 → 保存到数据库 → 更新任务状态
        │
        ▼
  用户轮询查询 → 返回结果（定位 + 修改建议 + 示例）
```

---

## 3. 规则 DSL 设计

### 3.1 设计原则

- **语义化而非位置化**：规则描述"要检查什么"，不指定具体单元格范围
- **统一格式**：技术人员和业务人员共用同一套 DSL
- **AI 辅助定位**：检查器在整个报告中搜索相关内容

### 3.2 DSL 整体结构

```json
{
  "report_type": "服务器交付报告",
  "version": "1.0",
  "description": "服务器交付报告的检查规则",
  "rules": [
    {
      "id": "rule_001",
      "name": "检查交付内容",
      "type": "text",
      "enabled": true,
      "config": {}
    }
  ]
}
```

### 3.3 五种检查类型

#### 3.3.1 文本检查（type: "text"）

在整个报告中搜索固定文字。

```json
{
  "id": "rule_001",
  "name": "检查交付内容标题",
  "type": "text",
  "enabled": true,
  "config": {
    "keywords": ["交付内容"],
    "match_mode": "any",
    "case_sensitive": false,
    "context_hint": "通常在报告的主体部分或章节标题中",
    "min_occurrences": 1
  }
}
```

- `match_mode`：`any`（任一关键词）| `all`（所有关键词）| `exact`（精确匹配）

#### 3.3.2 语义检查（type: "semantic"）

使用 AI 检查语义内容，AI 负责定位和验证。

```json
{
  "id": "rule_002",
  "name": "检查移交记录完整性",
  "type": "semantic",
  "enabled": true,
  "config": {
    "requirement": "移交记录中要包含移交人、移交时间、移交命令",
    "context_hint": "通常在报告的移交、交接或 handover 相关章节",
    "model": "text",
    "strict": true
  }
}
```

#### 3.3.3 图片检查（type: "image"）

使用多模态模型分析图片。

```json
{
  "id": "rule_003",
  "name": "检查机房清理照片",
  "type": "image",
  "enabled": true,
  "config": {
    "requirement": "清理后的机房，环境整洁干净",
    "context_hint": "通常在现场照片、机房环境或清理验收相关章节",
    "model": "multimodal",
    "min_match_count": 1,
    "image_filter": {
      "use_nearby_text": true,
      "keywords": ["机房", "清理", "现场"]
    }
  }
}
```

- `image_filter.use_nearby_text`：使用图片附近文字预筛选，命中关键词的图片优先检查
- `min_match_count`：至少匹配的图片数量

#### 3.3.4 API 检查（type: "api"）

先定位内容，再调用外部 API 验证。

```json
{
  "id": "rule_004",
  "name": "检查签名一致性",
  "type": "api",
  "enabled": true,
  "config": {
    "extract": {
      "type": "image",
      "description": "报告中的签名图片，通常在报告末尾或审批栏",
      "context_hint": "签名、审批、确认人等相关区域",
      "fallback": "last_image"
    },
    "api": {
      "name": "signature_validator",
      "endpoint": "https://api.example.com/validate-signature",
      "method": "POST",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      },
      "body": {
        "image": "${extracted_content}",
        "reference_id": "${report_id}"
      },
      "timeout": 10
    },
    "validation": {
      "success_condition": "response.status == 'valid'",
      "error_message": "签名验证失败"
    }
  }
}
```

#### 3.3.5 外部数据检查（type: "external_data"）

获取外部数据后结合 AI 分析。

```json
{
  "id": "rule_005",
  "name": "检查设备是否在清单中",
  "type": "external_data",
  "enabled": true,
  "config": {
    "extract": {
      "type": "text",
      "description": "报告中的设备列表，可能是表格或列表形式",
      "context_hint": "设备清单、设备列表、交付设备等相关章节",
      "parser": "ai_extract_list"
    },
    "external_api": {
      "name": "device_inventory",
      "endpoint": "https://api.example.com/devices/inventory",
      "method": "GET",
      "params": {
        "project_id": "${project_id}"
      },
      "response_path": "data.devices"
    },
    "analysis": {
      "type": "semantic",
      "requirement": "报告中的设备必须全部包含在外部清单中",
      "model": "text"
    }
  }
}
```

### 3.4 规则继承和覆盖

支持基础规则模板 + 用户自定义规则的组合：

```json
{
  "report_type": "服务器交付报告",
  "base_template": "standard_server_report_v1",
  "rules": []
}
```

用户自定义规则追加到基础规则后，`rule_id` 相同时覆盖基础规则。

---

## 4. 检查器实现

### 4.1 基类

```python
class BaseChecker(ABC):
    def __init__(self, report_data: ReportData, model_manager: ModelManager):
        self.report_data = report_data
        self.model_manager = model_manager

    @abstractmethod
    async def check(self, rule_config: Dict) -> CheckResult:
        pass

    async def locate_content(self, description: str, context_hint: str) -> List[Dict]:
        """使用 AI 定位内容（通用方法）"""
        summary = ReportSummarizer().summarize(self.report_data)
        prompt = f"""请在以下 Excel 报告中定位符合描述的内容。
描述：{description}
提示：{context_hint}

报告结构：
{summary}

请返回最可能包含该内容的单元格范围。"""
        response = await self.model_manager.call_text_model(prompt)
        return self._parse_location_response(response)
```

### 4.2 五种检查器

| 检查器 | 定位策略 | 检查策略 |
|--------|----------|----------|
| TextChecker | 全文关键词搜索（无需 AI） | 精确匹配 / 模糊匹配 |
| SemanticChecker | AI 定位相关章节 | AI 语义验证 |
| ImageChecker | 图片附近文字过滤 + 全部检查 | 多模态模型分析 |
| ApiChecker | AI 定位要提取的内容 | 调用外部 API + 条件验证 |
| ExternalDataChecker | AI 定位报告数据 | 外部 API 获取数据 + AI 对比分析 |

### 4.3 检查器工厂

```python
class CheckerFactory:
    CHECKER_MAP = {
        "text": TextChecker,
        "semantic": SemanticChecker,
        "image": ImageChecker,
        "api": ApiChecker,
        "external_data": ExternalDataChecker,
    }

    def __init__(self, report_data: ReportData, model_manager: ModelManager):
        self.report_data = report_data
        self.model_manager = model_manager

    def create(self, checker_type: str) -> BaseChecker:
        checker_class = self.CHECKER_MAP.get(checker_type)
        if not checker_class:
            raise ValueError(f"Unknown checker type: {checker_type}")
        return checker_class(self.report_data, self.model_manager)
```

---

## 5. AI 模型抽象层

### 5.1 架构

```
ModelManager
├── get_adapter(provider) -> BaseModelAdapter
├── call_text_model(prompt)        # 便捷方法
└── call_multimodal_model(prompt, image)  # 便捷方法

BaseModelAdapter (ABC)
├── call_text_model(prompt) -> str
├── call_multimodal_model(prompt, image) -> str
└── supports_model_type(model_type) -> bool

OpenAIAdapter(BaseModelAdapter)    # 基于 openai SDK
QwenAdapter(BaseModelAdapter)      # 基于 httpx，内部部署
```

### 5.2 配置

```yaml
# config/models.yaml
default_provider: openai

providers:
  openai:
    api_key: ${OPENAI_API_KEY}
    text_model: gpt-4
    multimodal_model: gpt-4-vision-preview
    base_url: https://api.openai.com/v1

  qwen:
    base_url: http://internal-qwen-api:8000
    api_key: ${QWEN_API_KEY}
    text_model: qwen-turbo
    multimodal_model: qwen-vl-plus
```

### 5.3 错误处理和重试

模型调用支持自动重试（默认 3 次），带简单退避策略。

---

## 6. Excel 解析器

### 6.1 设计

解析器提取两类数据：
- **单元格内容**：所有非空单元格的值和位置
- **图片**：图片数据、位置锚点、附近单元格文字

不做表格结构检测，由 AI 自行理解报告逻辑结构。

### 6.2 数据模型

```python
@dataclass
class CellData:
    row: int
    col: int
    value: Any
    cell_ref: str       # 如 "B3"
    data_type: str

@dataclass
class ImageData:
    id: str
    data: bytes
    format: str         # jpeg, png, etc.
    anchor: Dict        # 图片位置信息
    nearby_cells: List[CellData]

@dataclass
class ReportData:
    file_name: str
    sheet_name: str
    cells: List[CellData]
    images: List[ImageData]
    metadata: Dict[str, Any]
```

### 6.3 Token 优化策略

报告内容传给 AI 时需要控制 token 消耗：

1. **空行空列压缩**：跳过连续空白区域，不在摘要中生成无意义的位置信息
2. **内容截断**：单元格内容超过 200 字符时截断，保留前 200 字符 + "..."
3. **分块策略**：报告总文本超过阈值（如 4000 字符）时，按区域分块传给 AI，而非一次性全部传入
4. **按需加载**：AI 定位阶段传压缩摘要，验证阶段再传具体区域的完整内容

### 6.4 报告摘要生成

```python
class ReportSummarizer:
    MAX_CELL_LENGTH = 200
    MAX_SUMMARY_LENGTH = 4000

    def summarize(self, report_data: ReportData) -> str:
        """生成报告的结构化摘要，控制 token 消耗"""
        # 按行组织单元格内容，跳过空行，截断过长内容
        # 附加图片位置和附近文字信息
        pass

    def get_region(self, report_data: ReportData,
                   start_row: int, end_row: int) -> str:
        """获取指定区域的完整内容（用于验证阶段）"""
        pass
```

---

## 7. 数据模型和存储

### 7.1 数据库 Schema（SQLite）

```sql
-- 任务表
CREATE TABLE tasks (
    task_id TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    rules TEXT NOT NULL,          -- JSON
    report_type TEXT,
    status TEXT NOT NULL,         -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error TEXT
);

-- 检查结果表
CREATE TABLE check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    rule_id TEXT NOT NULL,
    rule_name TEXT NOT NULL,
    rule_type TEXT NOT NULL,
    status TEXT NOT NULL,         -- passed, failed, error
    location TEXT,               -- JSON
    message TEXT,
    suggestion TEXT,
    example TEXT,
    confidence REAL,
    execution_time REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
);

-- 规则模板表
CREATE TABLE rule_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    description TEXT,
    rules TEXT NOT NULL,          -- JSON
    version TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_check_results_task_id ON check_results(task_id);
```

### 7.2 文件存储

上传的 Excel 文件存储在 `data/uploads/{task_id}/` 目录下，任务完成后可定期清理。

### 7.3 缓存

图片检查结果使用内存缓存，键为 `md5(image_data) + md5(requirement)`，避免同一图片重复分析。

---

## 8. API 接口设计

### 8.1 提交检查任务

```
POST /api/v1/check/submit
Content-Type: multipart/form-data

参数：
  - file: Excel 文件（.xlsx）
  - rules: JSON 格式的规则 DSL 字符串
  - report_type: 报告类型（可选）

响应：
{
  "task_id": "uuid",
  "status": "pending",
  "message": "任务已提交，正在排队处理"
}
```

### 8.2 查询检查结果

```
GET /api/v1/check/result/{task_id}

响应：
{
  "task_id": "uuid",
  "status": "pending | processing | completed | failed",
  "progress": 60,
  "result": {                          // status 为 completed 时
    "report_info": {
      "file_name": "xxx.xlsx",
      "report_type": "服务器交付报告"
    },
    "results": [
      {
        "rule_id": "rule_001",
        "rule_name": "检查交付内容",
        "rule_type": "text",
        "status": "passed | failed | error",
        "location": {
          "type": "cell_range | image | not_found",
          "value": "B3",
          "context": "在'移交记录'章节中"
        },
        "message": "未找到'交付内容'字段",
        "suggestion": "请在报告中添加'交付内容'章节",
        "example": "交付内容：XXX 系统部署",
        "confidence": 0.95
      }
    ],
    "summary": {
      "total": 10,
      "passed": 8,
      "failed": 2,
      "error": 0
    }
  },
  "error": "错误信息"                   // status 为 failed 时
}
```

### 8.3 规则模板管理

```
GET  /api/v1/templates               # 列出模板
GET  /api/v1/templates/{template_id}  # 获取模板详情
```

### 8.4 错误处理

统一错误响应格式：

```json
{
  "error": {
    "code": "RULE_VALIDATION_ERROR",
    "message": "规则验证失败: 缺少 rules 字段"
  }
}
```

错误码：
- `RULE_VALIDATION_ERROR`：规则 DSL 格式或内容不合法
- `EXCEL_PARSE_ERROR`：Excel 文件解析失败
- `MODEL_ERROR`：AI 模型调用失败
- `INTERNAL_ERROR`：服务器内部错误

### 8.5 限流

提交接口限制每分钟 10 次请求（基于客户端 IP）。

---

## 9. 后台任务处理

### 9.1 任务队列

初期使用 Python asyncio 内存队列。未来可替换为 Redis / Celery。

### 9.2 后台工作进程

```python
class BackgroundWorker:
    async def _process_task(self, task_id: str):
        # 1. 更新状态为 processing              (进度 0%)
        # 2. 解析 Excel                         (进度 10%)
        # 3. 加载规则                            (进度 20%)
        # 4. 逐条执行规则检查                    (进度 20%-90%)
        # 5. 保存结果                            (进度 95%)
        # 6. 更新状态为 completed                (进度 100%)
        # 异常时更新状态为 failed，记录 error
```

---

## 10. 项目结构

```
report_check/
├── pyproject.toml
├── Dockerfile
├── docker-compose.yaml
│
├── config/
│   ├── models.yaml               # AI 模型配置
│   └── app.yaml                  # 应用配置
│
├── data/                         # 运行时数据
│   ├── reports.db
│   └── uploads/
│
├── logs/
│
├── src/
│   └── report_check/
│       ├── __init__.py
│       ├── main.py               # FastAPI 入口
│       │
│       ├── api/
│       │   ├── __init__.py
│       │   ├── router.py         # 路由定义
│       │   └── schemas.py        # Pydantic 模型
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── config.py         # 配置加载
│       │   ├── exceptions.py     # 自定义异常
│       │   └── logging.py        # 日志配置
│       │
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── rule_engine.py    # 规则引擎
│       │   └── validator.py      # 规则 DSL 验证
│       │
│       ├── checkers/
│       │   ├── __init__.py
│       │   ├── base.py           # 基类和 CheckResult
│       │   ├── factory.py        # 检查器工厂
│       │   ├── text.py
│       │   ├── semantic.py
│       │   ├── image.py
│       │   ├── api_check.py
│       │   └── external.py
│       │
│       ├── models/
│       │   ├── __init__.py
│       │   ├── base.py           # BaseModelAdapter
│       │   ├── manager.py        # ModelManager
│       │   ├── openai_adapter.py
│       │   └── qwen_adapter.py
│       │
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── excel.py          # ExcelParser
│       │   └── summarizer.py     # ReportSummarizer
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── database.py       # SQLite 数据访问层
│       │   ├── file.py           # FileStorage
│       │   └── cache.py          # ResultCache
│       │
│       └── worker/
│           ├── __init__.py
│           ├── queue.py          # TaskQueue
│           └── worker.py         # BackgroundWorker
│
├── tests/
│   ├── conftest.py
│   ├── test_api/
│   ├── test_checkers/
│   ├── test_engine/
│   ├── test_models/
│   └── test_parser/
│
├── frontend/                     # Vue 前端
│   ├── package.json
│   └── src/
│       ├── views/
│       │   ├── CheckPage.vue     # 检查页面
│       │   ├── ResultPage.vue    # 结果页面
│       │   └── RuleConfig.vue    # 规则配置页面
│       └── components/
│           ├── FileUpload.vue
│           ├── RuleEditor.vue
│           └── ResultTable.vue
│
└── docs/
```

---

## 11. 部署方案

### 11.1 Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src/ src/
COPY config/ config/

RUN mkdir -p data logs

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "report_check.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 11.2 docker-compose.yaml

```yaml
version: "3.8"

services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - QWEN_API_KEY=${QWEN_API_KEY}
      - MODEL_PROVIDER=${MODEL_PROVIDER:-openai}
    restart: unless-stopped
```

### 11.3 横向扩展

当前架构为无状态设计（数据存储在 SQLite），横向扩展时：
- 将 SQLite 替换为 PostgreSQL
- 将内存任务队列替换为 Redis / Celery
- 通过负载均衡分发请求到多个容器实例
