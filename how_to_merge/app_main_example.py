"""
项目 A 的接入示例代码。

假设：
- 项目 A 本身是 FastAPI
- A 使用 cfg 文件
- A 希望 report_check 跟随自己一起启动
- A 希望 report_check 路由挂到自己的前缀下
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from report_check.api.router import router as report_check_router
from report_check.bootstrap import init_report_check, shutdown_report_check
from report_check.settings import ReportCheckSettings

from cfg_example import cfg


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    report_check_settings = build_report_check_settings(cfg)
    await init_report_check(report_check_settings)
    yield
    await shutdown_report_check()


app = FastAPI(
    title="Project A",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/ping")
async def ping():
    return {"message": "pong"}


# A 的全局前缀
api_prefix = cfg["app"]["api_prefix"]

# report_check 在 A 里的子前缀
report_check_prefix = cfg["report_check"]["route_prefix"]

app.include_router(
    report_check_router,
    prefix=f"{api_prefix}{report_check_prefix}",
)


"""
接入后，典型接口地址如下：

- /api/v1/report-check/health
- /api/v1/report-check/check/submit
- /api/v1/report-check/check/result/{task_id}
- /api/v1/report-check/rules/validate

启动方式：

python -m uvicorn app_main_example:app --reload --host 0.0.0.0 --port 8000
"""
