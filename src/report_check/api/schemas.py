from pydantic import BaseModel
from typing import Any


class CheckSubmitResponse(BaseModel):
    task_id: str
    status: str
    message: str


class LocationInfo(BaseModel):
    type: str = ""
    value: str = ""
    context: str = ""


class CheckResultItem(BaseModel):
    rule_id: str
    rule_name: str
    rule_type: str
    status: str
    location: LocationInfo = LocationInfo()
    message: str = ""
    suggestion: str = ""
    example: str = ""
    confidence: float = 1.0


class CheckSummary(BaseModel):
    total: int
    passed: int
    failed: int
    error: int


class CheckResultData(BaseModel):
    report_info: dict[str, Any]
    results: list[CheckResultItem]
    summary: CheckSummary


class CheckResultResponse(BaseModel):
    task_id: str
    status: str
    progress: int = 0
    result: CheckResultData | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    queue_size: int
    version: str


class ValidationError(BaseModel):
    rule_id: str
    field: str
    message: str


class RuleValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = []


class ErrorResponse(BaseModel):
    error: dict[str, str]
