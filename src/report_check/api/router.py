import json
import uuid
import logging
import tempfile
import shutil
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
import zipfile
import io

from report_check.api.schemas import (
    CheckResultItem,
    CheckResultResponse,
    CheckResultData,
    CheckSubmitResponse,
    CheckSummary,
    HealthResponse,
    LocationInfo,
    RuleValidateResponse,
)
from report_check.core.exceptions import CheckError
from report_check.engine.validator import RuleValidator
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")
limiter = Limiter(key_func=get_remote_address)

EXCEL_MAGIC = b"PK"
PDF_MAGIC = b"%PDF"
MSG_MAGIC = b"\xD0\xCF\x11\xE0"  # MSG/OLE file magic
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@router.get("/health", response_model=HealthResponse)
async def health_check(request: Request):
    return HealthResponse(
        status="ok",
        queue_size=request.app.state.task_queue.size(),
        version="1.0.0",
    )


@router.post("/check/submit", response_model=CheckSubmitResponse)
@limiter.limit("10/minute")
async def submit_check(
    request: Request,
    files: list[UploadFile] = File(...),
    rules: str = Form(...),
    report_type: Optional[str] = Form(None),
    context_vars: Optional[str] = Form(None),
):
    if not files:
        raise HTTPException(status_code=400, detail="至少需要上传一个文件")

    # Validate all files
    file_data_list = []
    for f in files:
        if not f.filename or not f.filename.endswith((".xlsx", ".xls", ".pdf", ".msg")):
            raise HTTPException(status_code=400, detail=f"仅支持 .xlsx、.xls、.pdf 或 .msg 文件：{f.filename}")
        data = await f.read()
        if len(data) > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail=f"文件 {f.filename} 大小超过 20MB 限制")
        is_excel = data[:2] == EXCEL_MAGIC
        is_pdf = data[:4] == PDF_MAGIC
        is_msg = data[:4] == MSG_MAGIC
        if not (is_excel or is_pdf or is_msg):
            raise HTTPException(status_code=400, detail=f"文件格式不合法：{f.filename}")
        file_data_list.append((f.filename, data))

    # Parse rules
    try:
        rules_dict = json.loads(rules)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="规则 DSL 必须是有效的 JSON")

    # Validate rules DSL structure
    if not isinstance(rules_dict, dict):
        raise HTTPException(status_code=400, detail="规则 DSL 必须是 JSON 对象")

    # Parse context_vars
    ctx_vars = None
    if context_vars:
        try:
            ctx_vars = json.loads(context_vars)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="context_vars 必须是有效的 JSON")

    # Save files
    task_id = str(uuid.uuid4())
    primary_filename, primary_data = file_data_list[0]
    file_path = await request.app.state.file_storage.save_uploaded_file(
        primary_data, primary_filename, task_id
    )

    # Save extra files (if any)
    extra_file_paths = []
    for i, (fname, fdata) in enumerate(file_data_list[1:], start=1):
        extra_path = await request.app.state.file_storage.save_uploaded_file(
            fdata, f"extra_{i}_{fname}", task_id
        )
        extra_file_paths.append(extra_path)

    # Create task
    await request.app.state.db.create_task(
        task_id=task_id,
        file_name=primary_filename,
        file_path=file_path,
        rules=rules_dict,
        report_type=report_type,
        context_vars=ctx_vars,
        extra_file_paths=extra_file_paths,
    )

    # Enqueue
    await request.app.state.task_queue.enqueue(task_id)

    return CheckSubmitResponse(
        task_id=task_id,
        status="pending",
        message="任务已提交，正在排队处理",
    )


@router.get("/check/result/{task_id}", response_model=CheckResultResponse)
async def get_check_result(request: Request, task_id: str):
    task = await request.app.state.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    response = CheckResultResponse(
        task_id=task_id,
        status=task["status"],
        progress=task["progress"],
    )

    if task["status"] == "completed":
        results = await request.app.state.db.get_check_results(task_id)
        items = [
            CheckResultItem(
                rule_id=r["rule_id"],
                rule_name=r["rule_name"],
                rule_type=r["rule_type"],
                status=r["status"],
                location=LocationInfo(**r["location"]) if r.get("location") else LocationInfo(),
                message=r.get("message") or "",
                suggestion=r.get("suggestion") or "",
                example=r.get("example") or "",
                confidence=r.get("confidence") or 1.0,
            )
            for r in results
        ]
        summary = CheckSummary(
            total=len(items),
            passed=sum(1 for i in items if i.status == "passed"),
            failed=sum(1 for i in items if i.status == "failed"),
            error=sum(1 for i in items if i.status == "error"),
        )
        response.result = CheckResultData(
            report_info={
                "file_name": task["file_name"],
                "report_type": task.get("report_type"),
            },
            results=items,
            summary=summary,
        )

    if task["status"] == "failed":
        response.error = task.get("error")

    return response


@router.post("/rules/validate", response_model=RuleValidateResponse)
async def validate_rules(rules: dict):
    rule_list = rules.get("rules", [])
    if not isinstance(rule_list, list):
        return RuleValidateResponse(valid=False, errors=["'rules' must be a list"])

    all_errors = []
    required_fields = {"id", "name", "type"}
    valid_types = {"text", "semantic", "image", "api", "external_data", "multimodal_check", "signature_compare"}

    for i, rule in enumerate(rule_list):
        if not isinstance(rule, dict):
            all_errors.append(f"Rule {i}: must be a dict")
            continue
        for field in required_fields:
            if field not in rule:
                all_errors.append(f"Rule {i}: missing required field '{field}'")
        if "type" in rule and rule["type"] not in valid_types:
            all_errors.append(f"Rule {i}: unknown type '{rule['type']}'")

    return RuleValidateResponse(
        valid=len(all_errors) == 0,
        errors=all_errors,
    )


@router.get("/templates")
async def list_templates(request: Request, report_type: Optional[str] = None):
    templates = await request.app.state.db.get_rule_templates(report_type)
    return {"templates": templates}


@router.get("/templates/{template_id}")
async def get_template(request: Request, template_id: int):
    template = await request.app.state.db.get_rule_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


@router.get("/tasks/{task_id}/artifacts")
async def list_task_artifacts(request: Request, task_id: str):
    """List all artifacts for a task."""
    # Check if task exists
    task = await request.app.state.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # Check if artifacts manager is available
    if not hasattr(request.app.state, "artifacts_manager") or not request.app.state.artifacts_manager:
        raise HTTPException(status_code=404, detail="Artifacts 未启用")

    artifacts_path = request.app.state.artifacts_manager.base_path / task_id
    if not artifacts_path.exists():
        return {"task_id": task_id, "artifacts": []}

    def scan_directory(path: Path, rel_path: str = "") -> list:
        """Recursively scan directory and return file list."""
        items = []
        try:
            for item in sorted(path.iterdir()):
                item_rel = f"{rel_path}/{item.name}" if rel_path else item.name
                if item.is_dir():
                    items.append({
                        "name": item.name,
                        "type": "directory",
                        "path": item_rel,
                        "children": scan_directory(item, item_rel)
                    })
                else:
                    items.append({
                        "name": item.name,
                        "type": "file",
                        "path": item_rel,
                        "size": item.stat().st_size,
                    })
        except Exception as e:
            logger.warning(f"Failed to scan directory {path}: {e}")
        return items

    return {
        "task_id": task_id,
        "artifacts": scan_directory(artifacts_path)
    }


@router.get("/tasks/{task_id}/artifacts/download")
async def download_task_artifacts(request: Request, task_id: str, background_tasks: BackgroundTasks):
    """Download all artifacts for a task as a zip file."""
    # Check if task exists
    task = await request.app.state.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # Check if artifacts manager is available
    if not hasattr(request.app.state, "artifacts_manager") or not request.app.state.artifacts_manager:
        raise HTTPException(status_code=404, detail="Artifacts 未启用")

    artifacts_path = request.app.state.artifacts_manager.base_path / task_id
    if not artifacts_path.exists():
        raise HTTPException(status_code=404, detail="该任务没有 artifacts")

    # Create temp file for the zip
    with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
        tmp_path = tmp.name

    # Create zip archive
    zip_path = shutil.make_archive(tmp_path[:-4], "zip", artifacts_path)

    # Clean up temp file after streaming
    def cleanup():
        try:
            os.unlink(zip_path)
        except Exception:
            pass

    background_tasks.add_task(cleanup)

    return FileResponse(
        zip_path,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={task_id}_artifacts.zip"},
    )


@router.get("/tasks/{task_id}/artifacts/{file_path:path}")
async def get_task_artifact(request: Request, task_id: str, file_path: str):
    """Get a specific artifact file."""
    # Check if task exists
    task = await request.app.state.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # Check if artifacts manager is available
    if not hasattr(request.app.state, "artifacts_manager") or not request.app.state.artifacts_manager:
        raise HTTPException(status_code=404, detail="Artifacts 未启用")

    artifacts_path = request.app.state.artifacts_manager.base_path / task_id
    file_full_path = artifacts_path / file_path

    # Security check: ensure the file is within the task's artifacts directory
    try:
        file_full_path.resolve().relative_to(artifacts_path.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="访问被拒绝")

    if not file_full_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")

    if file_full_path.is_dir():
        raise HTTPException(status_code=400, detail="路径是目录，请使用 list 接口")

    # Determine content type
    content_type = "application/octet-stream"
    if file_path.endswith(".json"):
        content_type = "application/json"
    elif file_path.endswith(".txt"):
        content_type = "text/plain"
    elif file_path.endswith(".png"):
        content_type = "image/png"
    elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
        content_type = "image/jpeg"
    elif file_path.endswith(".xlsx"):
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif file_path.endswith(".pdf"):
        content_type = "application/pdf"
    elif file_path.endswith(".msg"):
        content_type = "application/vnd.ms-outlook"

    return FileResponse(file_full_path, media_type=content_type, filename=file_full_path.name)
