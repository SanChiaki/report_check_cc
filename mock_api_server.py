"""Mock API Server for testing report check system.

Provides three endpoints:
1. GET /devices/list - Returns device inventory
2. POST /signature/verify - Verifies signature images
3. POST /email/verify - Verifies email addresses
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import base64
import re

app = FastAPI(title="Mock API Server", version="1.0.0")


# Models
class SignatureVerifyRequest(BaseModel):
    image: str  # base64 encoded image
    type: str = "signature"


class EmailVerifyRequest(BaseModel):
    email: str


# Mock device inventory
DEVICE_INVENTORY = [
    "信号塔设备-ST-001",
    "信号塔设备-ST-002",
    "路由器-RT-5G-100",
    "路由器-RT-5G-101",
    "天线-ANT-2.4G-50",
    "天线-ANT-5G-80",
    "电源模块-PWR-220V-01",
    "控制器-CTRL-Master-01",
]


@app.get("/")
async def root():
    return {
        "service": "Mock API Server",
        "version": "1.0.0",
        "endpoints": [
            "GET /devices/list",
            "POST /signature/verify",
            "POST /email/verify",
        ],
    }


@app.get("/devices/list")
async def get_devices():
    """Return mock device inventory."""
    return {
        "status": "success",
        "data": {
            "devices": DEVICE_INVENTORY,
            "total": len(DEVICE_INVENTORY),
            "updated_at": "2026-03-23T10:00:00Z",
        },
    }


@app.post("/signature/verify")
async def verify_signature(request: SignatureVerifyRequest):
    """Verify signature image (mock implementation)."""
    try:
        # Decode base64 to check if it's valid
        image_data = base64.b64decode(request.image)

        # Mock logic: images larger than 10KB are considered valid signatures
        is_valid = len(image_data) > 10240

        return {
            "status": "success",
            "verified": is_valid,
            "confidence": 0.95 if is_valid else 0.3,
            "message": "签名验证通过" if is_valid else "签名验证失败",
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {str(e)}")


@app.post("/email/verify")
async def verify_email(request: EmailVerifyRequest):
    """Verify email address (mock implementation)."""
    email = request.email.strip()

    # Basic email regex validation
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    is_valid_format = re.match(email_pattern, email) is not None

    # Mock logic: only allow certain domains
    allowed_domains = ["example.com", "company.com", "test.com", "gmail.com"]
    domain = email.split("@")[-1] if "@" in email else ""
    is_allowed_domain = domain in allowed_domains

    is_valid = is_valid_format and is_allowed_domain

    return {
        "status": "success",
        "valid": is_valid,
        "email": email,
        "message": "邮箱验证通过" if is_valid else "邮箱验证失败",
        "reason": "" if is_valid else f"域名 {domain} 不在允许列表中" if is_valid_format else "邮箱格式不正确",
    }


if __name__ == "__main__":
    print("Starting Mock API Server on http://localhost:8001")
    print("Available endpoints:")
    print("  GET  http://localhost:8001/devices/list")
    print("  POST http://localhost:8001/signature/verify")
    print("  POST http://localhost:8001/email/verify")
    uvicorn.run(app, host="0.0.0.0", port=8001)
