import json


def test_submit_msg_file(client):
    msg_content = b"\xD0\xCF\x11\xE0" + b"\x00" * 100

    rules = {
        "rules": [
            {
                "id": "r1",
                "name": "检查邮件正文",
                "type": "text",
                "config": {"field": "email_body", "keywords": ["测试"]},
            }
        ]
    }

    response = client.post(
        "/api/v1/check/submit",
        files={"files": ("test.msg", msg_content, "application/vnd.ms-outlook")},
        data={"rules": json.dumps(rules)},
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"


def test_msg_file_validation(client):
    response = client.post(
        "/api/v1/check/submit",
        files={"files": ("test.txt", b"dummy", "text/plain")},
        data={"rules": '{"rules": []}'},
    )

    assert response.status_code == 400
    assert ".msg" in response.json()["detail"]


def test_msg_file_magic_validation(client):
    response = client.post(
        "/api/v1/check/submit",
        files={"files": ("test.msg", b"invalid", "application/vnd.ms-outlook")},
        data={"rules": '{"rules": []}'},
    )

    assert response.status_code == 400
    assert "文件格式不合法" in response.json()["detail"]
