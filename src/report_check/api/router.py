import json
import uuid
import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from typing import Optional

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
    file: UploadFile = File(...),
    rules: str = Form(...),
    report_type: Optional[str] = Form(None),
    context_vars: Optional[str] = Form(None),
):
    # Validate file extension
    if not file.filename or not file.filename.endswith((".xlsx", ".xls", ".pdf")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx、.xls 或 .pdf 文件")

    # Read file
    file_data = await file.read()

    # Validate file size
    if len(file_data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小超过 20MB 限制")

    # Validate magic bytes
    is_excel = file_data[:2] == EXCEL_MAGIC
    is_pdf = file_data[:4] == PDF_MAGIC
    if not (is_excel or is_pdf):
        raise HTTPException(status_code=400, detail="文件格式不合法")

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

    # Save file
    task_id = str(uuid.uuid4())
    file_path = await request.app.state.file_storage.save_uploaded_file(
        file_data, file.filename, task_id
    )

    # Create task
    await request.app.state.db.create_task(
        task_id=task_id,
        file_name=file.filename,
        file_path=file_path,
        rules=rules_dict,
        report_type=report_type,
        context_vars=ctx_vars,
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
    valid_types = {"text", "semantic", "image", "api", "external_data"}

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
