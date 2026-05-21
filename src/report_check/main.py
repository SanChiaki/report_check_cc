import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from report_check.api.router import router
from report_check.bootstrap import init_report_check, shutdown_report_check
from report_check.core.config import load_config
from report_check.core.exceptions import CheckError
from report_check.settings import ReportCheckSettings

project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=project_root / ".env")

logger = logging.getLogger(__name__)
_standalone_settings_loader = load_standalone_settings if "load_standalone_settings" in globals() else None


def set_standalone_settings_loader(loader):
    global _standalone_settings_loader
    _standalone_settings_loader = loader


def load_standalone_settings() -> ReportCheckSettings:
    config_path = Path("config/models.yaml")
    if config_path.exists():
        model_config = load_config(str(config_path))
    else:
        model_config = {"default_provider": "openai", "providers": {}}

    app_config_path = Path("config/app.yaml")
    if app_config_path.exists():
        app_config = load_config(str(app_config_path))
    else:
        app_config = {"storage": {"upload_path": "data/uploads"}}

    return ReportCheckSettings.from_mapping(app_config=app_config, model_config=model_config)


@asynccontextmanager
async def lifespan(app: FastAPI):
    loader = _standalone_settings_loader or load_standalone_settings
    settings = loader()
    runtime = await init_report_check(settings)
    app.state.report_check_runtime = runtime

    yield

    await shutdown_report_check()


app = FastAPI(
    title="报告一致性检查系统",
    description="AI 驱动的 Excel/PDF/MSG 报告自动检查服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.exception_handler(CheckError)
async def check_error_handler(request: Request, exc: CheckError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
