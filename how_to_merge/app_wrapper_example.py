"""
项目 A 对 report_check 再包一层的示例代码。

目标：
- 保留 A 自己的统一鉴权
- 保留 A 自己的统一限流
- 保留 A 自己的统一异常格式
- 不直接把 report_check 的原始 router 裸挂出去

说明：
- 这是示例骨架，重点是接入模式
- 可根据 A 的现有依赖注入体系、异常体系、限流体系调整
"""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from report_check.bootstrap import init_report_check, shutdown_report_check
from report_check.runtime import get_runtime
from report_check.settings import ReportCheckSettings

from cfg_example import cfg


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: dict | list | str | None = None


class ApiError(Exception):
    def __init__(self, code: int, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def build_report_check_settings(cfg_dict: dict) -> ReportCheckSettings:
    report_cfg = cfg_dict["report_check"]
    return ReportCheckSettings(
        upload_path=report_cfg["upload_path"],
        artifacts_path=report_cfg["artifacts_path"],
        max_waiting_tasks=report_cfg.get("max_waiting_tasks", 10),
        worker_concurrency=report_cfg.get("worker_concurrency", 1),
        per_task_rule_concurrency=report_cfg.get("per_task_rule_concurrency", 1),
        default_provider=report_cfg.get("default_provider", "openai"),
        providers=report_cfg.get("providers", {}),
        external_api_limits=report_cfg.get("external_api_limits", {}),
    )


async def verify_token():
    """
    项目 A 的统一鉴权示例。

    这里仅演示结构，实际可替换为：
    - JWT 校验
    - session 校验
    - API key 校验
    - RBAC 权限校验
    """
    return {"user_id": "demo-user"}


def apply_rate_limit():
    """
    项目 A 的统一限流示例。

    这里不写具体实现，实际项目里可替换为：
    - Redis 限流
    - 网关限流
    - 自己的 decorator / dependency
    """
    return True


CurrentUser = Annotated[dict, Depends(verify_token)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    report_check_settings = build_report_check_settings(cfg)
    await init_report_check(report_check_settings)
    yield
    await shutdown_report_check()


app = FastAPI(
    title="Project A Wrapped Example",
    version="1.0.0",
    lifespan=lifespan,
)


@app.exception_handler(ApiError)
async def api_error_handler(request, exc: ApiError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "data": None,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.status_code,
            "message": str(exc.detail),
            "data": None,
        },
    )


report_check_router = APIRouter(prefix="/api/v1/report-check", tags=["report-check"])


@report_check_router.get("/health", response_model=ApiResponse)
async def report_check_health(user: CurrentUser):
    runtime = get_runtime()
    stats = runtime.model_manager.get_inflight_stats()
    return ApiResponse(
        data={
            "status": "ok",
            "queue_size": runtime.task_queue.size(),
            "running_tasks": runtime.worker.running_tasks,
            "model_inflight": stats["model_inflight"],
            "model_text_inflight": stats["model_text_inflight"],
            "model_multimodal_inflight": stats["model_multimodal_inflight"],
            "version": "1.0.0",
        }
    )


@report_check_router.post("/check/submit", response_model=ApiResponse)
async def wrapped_submit_check(
    user: CurrentUser,
    files: list[UploadFile] = File(...),
    rules: str = Form(...),
    report_type: str | None = Form(None),
    context_vars: str | None = Form(None),
):
    apply_rate_limit()
    runtime = get_runtime()

    if not files:
        raise ApiError(code=40001, message="至少需要上传一个文件", status_code=400)

    file_data_list = []
    for f in files:
        if not f.filename or not f.filename.endswith((".xlsx", ".xls", ".pdf", ".msg")):
            raise ApiError(code=40002, message=f"不支持的文件类型: {f.filename}", status_code=400)
        data = await f.read()
        file_data_list.append((f.filename, data))

    import json
    import uuid

    try:
        rules_dict = json.loads(rules)
    except json.JSONDecodeError:
        raise ApiError(code=40003, message="rules 必须是合法 JSON", status_code=400)

    parsed_context_vars = None
    if context_vars:
        try:
            parsed_context_vars = json.loads(context_vars)
        except json.JSONDecodeError:
            raise ApiError(code=40004, message="context_vars 必须是合法 JSON", status_code=400)

    task_id = str(uuid.uuid4())
    primary_filename, primary_data = file_data_list[0]
    file_path = await runtime.file_storage.save_uploaded_file(
        primary_data, primary_filename, task_id
    )

    extra_file_paths = []
    for i, (fname, fdata) in enumerate(file_data_list[1:], start=1):
        extra_path = await runtime.file_storage.save_uploaded_file(
            fdata, f"extra_{i}_{fname}", task_id
        )
        extra_file_paths.append(extra_path)

    await runtime.task_store.create_task(
        task_id=task_id,
        file_name=primary_filename,
        file_path=file_path,
        rules=rules_dict,
        report_type=report_type,
        context_vars=parsed_context_vars,
        extra_file_paths=extra_file_paths,
    )

    if not runtime.task_queue.try_enqueue(task_id):
        await runtime.task_store.delete_task(task_id)
        await runtime.file_storage.cleanup_task_files(task_id)
        raise ApiError(code=42901, message="等待队列已满，请稍后重试", status_code=429)

    return ApiResponse(
        data={
            "task_id": task_id,
            "status": "pending",
            "message": "任务已提交，正在排队处理",
        }
    )


@report_check_router.get("/check/result/{task_id}", response_model=ApiResponse)
async def wrapped_get_check_result(task_id: str, user: CurrentUser):
    apply_rate_limit()
    runtime = get_runtime()
    task = await runtime.task_store.get_task(task_id)
    if not task:
        raise ApiError(code=40401, message=f"任务不存在: {task_id}", status_code=404)

    response = {
        "task_id": task_id,
        "status": task["status"],
        "progress": task["progress"],
        "result": None,
        "error": task.get("error"),
    }

    if task["status"] == "completed":
        results = await runtime.task_store.get_check_results(task_id)
        response["result"] = {
            "report_info": {
                "file_name": task["file_name"],
                "report_type": task.get("report_type"),
            },
            "results": results,
            "summary": {
                "total": len(results),
                "passed": sum(1 for i in results if i["status"] == "passed"),
                "failed": sum(1 for i in results if i["status"] == "failed"),
                "error": sum(1 for i in results if i["status"] == "error"),
            },
        }

    return ApiResponse(data=response)


@report_check_router.post("/rules/validate", response_model=ApiResponse)
async def wrapped_validate_rules(rules: dict, user: CurrentUser):
    apply_rate_limit()

    rule_list = rules.get("rules", [])
    if not isinstance(rule_list, list):
        return ApiResponse(
            data={
                "valid": False,
                "errors": [{"rule_id": "", "field": "rules", "message": "'rules' must be a list"}],
            }
        )

    required_fields = {"id", "name", "type"}
    valid_types = {
        "text",
        "semantic",
        "image",
        "api",
        "external_data",
        "multimodal_check",
        "signature_compare",
        "image_consistency",
    }

    errors = []
    for i, rule in enumerate(rule_list):
        rule_id = rule.get("id", f"r{i}") if isinstance(rule, dict) else f"r{i}"
        if not isinstance(rule, dict):
            errors.append({"rule_id": rule_id, "field": "", "message": "must be a dict"})
            continue
        for field in required_fields:
            if field not in rule:
                errors.append({"rule_id": rule_id, "field": field, "message": f"missing required field '{field}'"})
        if "type" in rule and rule["type"] not in valid_types:
            errors.append({"rule_id": rule_id, "field": "type", "message": f"unknown type '{rule['type']}'"})

    return ApiResponse(
        data={
            "valid": len(errors) == 0,
            "errors": errors,
        }
    )


app.include_router(report_check_router)


"""
这一版的特点：

1. 不直接 include report_check 原始 router
2. 所有接口都先经过 A 的鉴权 dependency
3. 可以统一做 A 的限流
4. 可以统一包装返回结构
5. 可以统一异常码和异常格式

适用场景：

- A 已经有自己的响应协议
- A 已经有自己的认证体系
- A 不希望 report_check 暴露自己的原始 HTTP 风格
"""
