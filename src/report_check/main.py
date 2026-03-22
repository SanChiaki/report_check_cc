import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from report_check.api.router import router
from report_check.core.config import load_config
from report_check.core.exceptions import CheckError
from report_check.models.manager import ModelManager
from report_check.models.openai_adapter import OpenAIAdapter
from report_check.models.qwen_adapter import QwenAdapter
from report_check.storage.database import Database
from report_check.storage.file import FileStorage
from report_check.worker.queue import TaskQueue
from report_check.worker.worker import BackgroundWorker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load config
    config_path = Path("config/models.yaml")
    if config_path.exists():
        model_config = load_config(str(config_path))
    else:
        model_config = {"default_provider": "openai", "providers": {}}

    app_config_path = Path("config/app.yaml")
    if app_config_path.exists():
        app_config = load_config(str(app_config_path))
    else:
        app_config = {"storage": {"database_path": "data/reports.db", "upload_path": "data/uploads"}}

    storage_config = app_config.get("storage", {})

    # Ensure data directories exist
    Path(storage_config.get("database_path", "data/reports.db")).parent.mkdir(parents=True, exist_ok=True)

    # Init components
    app.state.db = Database(storage_config.get("database_path", "data/reports.db"))
    app.state.file_storage = FileStorage(storage_config.get("upload_path", "data/uploads"))
    app.state.task_queue = TaskQueue()

    # Init model manager
    model_manager = ModelManager(
        default_provider=model_config.get("default_provider", "openai")
    )
    for name, cfg in model_config.get("providers", {}).items():
        if name == "openai":
            model_manager.register_adapter(name, OpenAIAdapter(cfg))
        elif name == "qwen":
            model_manager.register_adapter(name, QwenAdapter(cfg))

    app.state.model_manager = model_manager

    # Start worker
    app.state.worker = BackgroundWorker(
        db=app.state.db,
        model_manager=model_manager,
        task_queue=app.state.task_queue,
    )
    await app.state.worker.start()

    yield

    await app.state.worker.stop()


app = FastAPI(
    title="报告一致性检查系统",
    description="AI 驱动的 Excel 报告自动检查服务",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(router)


@app.exception_handler(CheckError)
async def check_error_handler(request: Request, exc: CheckError):
    return JSONResponse(
        status_code=400,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
