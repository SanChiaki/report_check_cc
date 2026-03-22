import json
import pytest
from pathlib import Path
from io import BytesIO

from fastapi.testclient import TestClient

from report_check.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "queue_size" in data
        assert "version" in data


class TestSubmitEndpoint:
    def test_submit_valid(self, client, sample_excel_path):
        rules = json.dumps({
            "rules": [
                {"id": "r1", "name": "test", "type": "text", "config": {"keywords": ["交付"]}}
            ]
        })
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"rules": rules},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "pending"
        assert "message" in data

    def test_submit_invalid_extension(self, client):
        resp = client.post(
            "/api/v1/check/submit",
            files={"file": ("test.txt", BytesIO(b"hello"), "text/plain")},
            data={"rules": "{}"},
        )
        assert resp.status_code == 400

    def test_submit_invalid_rules(self, client, sample_excel_path):
        with open(sample_excel_path, "rb") as f:
            resp = client.post(
                "/api/v1/check/submit",
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"rules": "not json"},
            )
        assert resp.status_code == 400


class TestResultEndpoint:
    def test_result_not_found(self, client):
        resp = client.get("/api/v1/check/result/nonexistent-task-id")
        assert resp.status_code == 404


class TestValidateEndpoint:
    def test_validate_valid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1", "name": "t", "type": "text", "config": {"keywords": ["x"]}}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_validate_invalid_rules(self, client):
        resp = client.post(
            "/api/v1/rules/validate",
            json={"rules": [{"id": "r1"}]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0
