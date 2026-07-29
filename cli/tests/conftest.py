import json

import httpx
import pytest


class FakeAPI:
    """Records requests and returns canned httpx responses."""

    def __init__(self):
        self.calls = []
        self.response_status = 200
        self.response_body: dict = {}
        self.raise_connect_error = False

    def handler(self, method, url, **kwargs):
        if self.raise_connect_error:
            raise httpx.ConnectError("connection refused")
        self.calls.append({
            "method": method,
            "url": url,
            "json": kwargs.get("json"),
            "params": kwargs.get("params"),
            "headers": kwargs.get("headers") or {},
        })
        return httpx.Response(
            self.response_status,
            content=json.dumps(self.response_body).encode(),
            headers={"Content-Type": "application/json"},
            request=httpx.Request(method, url),
        )


@pytest.fixture
def api(monkeypatch):
    fake = FakeAPI()
    monkeypatch.setattr(httpx, "request", fake.handler)
    monkeypatch.setenv("AGENT_DECK_URL", "http://127.0.0.1:8765")
    monkeypatch.setenv("AGENT_DECK_WRITE_TOKEN", "secret-token")
    return fake


TASK_BODY = {
    "id": 1, "public_id": "REM-104", "title": "Fix DOCX table import",
    "status": "running", "priority": "normal", "tests_status": "pending",
    "build_status": "pending", "project": {"name": "CrowForge", "slug": "crowforge"},
    "agent_type": "claude", "branch": "agent/rem-104-docx",
    "result_summary": None, "error_message": None,
}
