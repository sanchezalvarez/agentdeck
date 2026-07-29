import pytest

from agent_report.cli import main

from .conftest import TASK_BODY


def test_create_success(api, capsys):
    api.response_status = 201
    api.response_body = dict(TASK_BODY, status="queued")
    code = main([
        "create", "--title", "Fix DOCX table import",
        "--description", "Table borders and alignment are lost.",
        "--project", "crowforge", "--agent", "claude", "--requested-by", "Lubomir",
    ])
    assert code == 0
    out = capsys.readouterr().out
    assert "REM-104" in out
    call = api.calls[0]
    assert call["method"] == "POST"
    assert call["url"].endswith("/api/tasks")
    assert call["json"]["agent_type"] == "claude"
    assert call["json"]["requested_by"] == "Lubomir"
    assert call["headers"]["Authorization"] == "Bearer secret-token"


def test_start_sends_payload(api, capsys):
    api.response_body = TASK_BODY
    code = main([
        "start", "--task", "REM-104", "--agent", "claude", "--project", "crowforge",
        "--branch", "agent/rem-104-docx",
        "--working-directory", "D:\\AgentWorkspaces\\crowforge-claude",
    ])
    assert code == 0
    call = api.calls[0]
    assert call["url"].endswith("/api/tasks/REM-104/start")
    assert call["json"]["branch"] == "agent/rem-104-docx"
    assert "process_id" not in call["json"]  # None values are dropped


def test_progress_with_metadata(api):
    api.response_body = TASK_BODY
    code = main([
        "progress", "--task", "REM-104", "--message", "Implemented parsing",
        "--status", "testing", "--metadata-json", '{"files": 3}',
    ])
    assert code == 0
    call = api.calls[0]
    assert call["json"] == {"message": "Implemented parsing", "status": "testing",
                            "metadata": {"files": 3}}


def test_testing_command(api):
    api.response_body = dict(TASK_BODY, tests_status="passed")
    code = main(["testing", "--task", "REM-104", "--kind", "tests",
                 "--status", "passed", "--message", "42 tests passed"])
    assert code == 0
    assert api.calls[0]["url"].endswith("/api/tasks/REM-104/testing")


def test_finish_command(api, capsys):
    api.response_body = dict(TASK_BODY, status="needs_review")
    code = main([
        "finish", "--task", "REM-104", "--summary", "Implemented fixes.",
        "--branch", "agent/rem-104-docx", "--commit", "a94c2e1",
        "--tests", "passed", "--build", "passed", "--exit-code", "0",
    ])
    assert code == 0
    assert "needs_review" in capsys.readouterr().out
    body = api.calls[0]["json"]
    assert body["commit"] == "a94c2e1"
    assert body["exit_code"] == 0


def test_fail_command(api):
    api.response_body = dict(TASK_BODY, status="failed")
    code = main(["fail", "--task", "REM-104", "--error", "Tests failed.",
                 "--tests", "failed", "--build", "not_run", "--exit-code", "1"])
    assert code == 0
    assert api.calls[0]["json"]["error"] == "Tests failed."


def test_block_command(api):
    api.response_body = dict(TASK_BODY, status="blocked")
    code = main(["block", "--task", "REM-104", "--reason", "Missing client document."])
    assert code == 0
    assert api.calls[0]["json"] == {"reason": "Missing client document."}


def test_artifact_command(api):
    api.response_status = 201
    api.response_body = {"id": 7, "name": "Preview", "task_id": 1}
    code = main(["artifact", "--task", "REM-104", "--type", "screenshot",
                 "--name", "Preview", "--path", "D:\\artifacts\\preview.png"])
    assert code == 0
    assert api.calls[0]["json"]["local_path"] == "D:\\artifacts\\preview.png"


def test_heartbeat_bool_parsing(api):
    api.response_body = {"name": "Rembrosoft-Main-PC", "status": "online",
                         "last_seen_at": "2026-07-19T10:00:00"}
    code = main(["heartbeat", "--worker", "Rembrosoft-Main-PC",
                 "--claude-available", "true", "--codex-available", "true",
                 "--unity-available", "true", "--unity-mcp-available", "false"])
    assert code == 0
    body = api.calls[0]["json"]
    assert body["claude_available"] is True
    assert body["unity_mcp_available"] is False


def test_status_command(api, capsys):
    api.response_body = TASK_BODY

    def handler(method, url, **kwargs):
        api.calls.append({"method": method, "url": url})
        import httpx as _httpx
        import json as _json
        body = TASK_BODY if url.endswith("/api/tasks/REM-104") else {"items": [
            {"id": 1, "task_id": 1, "event_type": "task_started",
             "message": "Agent started", "metadata": None,
             "created_at": "2026-07-19T10:00:00"}], "total": 1, "limit": 5, "offset": 0}
        return _httpx.Response(200, content=_json.dumps(body).encode(),
                               headers={"Content-Type": "application/json"},
                               request=_httpx.Request(method, url))

    import httpx
    import agent_report.client  # noqa: F401
    original = httpx.request
    httpx.request = handler
    try:
        code = main(["status", "--task", "REM-104"])
    finally:
        httpx.request = original
    assert code == 0
    out = capsys.readouterr().out
    assert "REM-104" in out
    assert "task_started" in out


def test_json_output(api, capsys):
    api.response_body = TASK_BODY
    code = main(["start", "--task", "REM-104", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    assert '"public_id": "REM-104"' in out


def test_api_error_returns_nonzero(api, capsys):
    api.response_status = 404
    api.response_body = {"detail": "Task 'REM-999' not found"}
    code = main(["start", "--task", "REM-999"])
    assert code == 1
    err = capsys.readouterr().err
    assert "not found" in err
    assert "secret-token" not in err  # never leak the token


def test_connection_error_returns_exit_3(api, capsys):
    api.raise_connect_error = True
    code = main(["progress", "--task", "REM-104", "--message", "hello"])
    assert code == 3
    assert "Could not reach Agent Deck" in capsys.readouterr().err


def test_missing_required_argument_exits_2(api):
    with pytest.raises(SystemExit) as excinfo:
        main(["progress", "--task", "REM-104"])  # --message missing
    assert excinfo.value.code == 2


def test_invalid_choice_exits_2(api):
    with pytest.raises(SystemExit) as excinfo:
        main(["testing", "--task", "REM-104", "--kind", "tests", "--status", "bogus"])
    assert excinfo.value.code == 2


def test_invalid_metadata_json_exits_2(api):
    with pytest.raises(SystemExit) as excinfo:
        main(["progress", "--task", "REM-104", "--message", "x",
              "--metadata-json", "{not json"])
    assert excinfo.value.code == 2


def test_invalid_bool_exits_2(api):
    with pytest.raises(SystemExit) as excinfo:
        main(["heartbeat", "--worker", "PC", "--claude-available", "maybe"])
    assert excinfo.value.code == 2
