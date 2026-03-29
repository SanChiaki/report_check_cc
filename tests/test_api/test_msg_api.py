"""MSG 文件 API 集成测试"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json


@pytest.mark.asyncio
async def test_submit_msg_file(test_client):
    """测试提交 MSG 文件"""
    # 创建模拟的 MSG 文件
    msg_content = b"\xD0\xCF\x11\xE0" + b"\x00" * 100  # MSG magic + dummy data

    # 模拟规则
    rules = {
        "rules": [
            {
                "id": "r1",
                "name": "检查邮件正文",
                "type": "text",
                "config": {"field": "email_body", "keywords": ["测试"]}
            }
        ]
    }

    # 提交请求
    response = await test_client.post(
        "/api/v1/check/submit",
        files={"files": ("test.msg", msg_content, "application/vnd.ms-outlook")},
        data={"rules": json.dumps(rules)}
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_msg_file_validation(test_client):
    """测试 MSG 文件格式验证"""
    # 错误的文件扩展名
    response = await test_client.post(
        "/api/v1/check/submit",
        files={"files": ("test.txt", b"dummy", "text/plain")},
        data={"rules": '{"rules": []}'}
    )

    assert response.status_code == 400
    assert "仅支持" in response.json()["detail"]


@pytest.mark.asyncio
async def test_msg_file_magic_validation(test_client):
    """测试 MSG 文件 magic number 验证"""
    # 正确的扩展名但错误的 magic number
    response = await test_client.post(
        "/api/v1/check/submit",
        files={"files": ("test.msg", b"invalid", "application/vnd.ms-outlook")},
        data={"rules": '{"rules": []}'}
    )

    assert response.status_code == 400
    assert "文件格式不合法" in response.json()["detail"]
