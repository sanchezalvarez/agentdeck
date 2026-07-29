def test_create_task_generates_sequential_public_ids(client, auth, project):
    ids = []
    for i in range(3):
        response = client.post(
            "/api/tasks", json={"title": f"Task {i}", "project": "crowforge"}, headers=auth
        )
        assert response.status_code == 201
        ids.append(response.json()["public_id"])
    assert ids == ["REM-001", "REM-002", "REM-003"]


def test_create_task_defaults(client, auth, task):
    assert task["status"] == "queued"
    assert task["priority"] == "normal"
    assert task["tests_status"] == "pending"
    assert task["project"]["slug"] == "crowforge"
    events = client.get(f"/api/tasks/{task['public_id']}/events").json()["items"]
    assert events[0]["event_type"] == "task_created"


def test_create_task_unknown_project(client, auth):
    response = client.post(
        "/api/tasks", json={"title": "X", "project": "nope"}, headers=auth
    )
    assert response.status_code == 404


def test_get_task_by_public_id_and_numeric_id(client, task):
    by_public = client.get("/api/tasks/REM-001")
    assert by_public.status_code == 200
    by_id = client.get(f"/api/tasks/{task['id']}")
    assert by_id.status_code == 200
    assert by_public.json()["id"] == by_id.json()["id"]
    # Case-insensitive public id
    assert client.get("/api/tasks/rem-001").status_code == 200
    assert client.get("/api/tasks/REM-999").status_code == 404


def test_start_task(client, auth, task):
    response = client.post(
        f"/api/tasks/{task['public_id']}/start",
        json={"agent_type": "claude", "worker": "Rembrosoft-Main-PC",
              "branch": "agent/rem-001-docx", "process_id": 4242,
              "working_directory": "D:\\AgentWorkspaces\\crowforge-claude"},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["started_at"] is not None
    assert body["branch"] == "agent/rem-001-docx"
    assert body["worker"]["name"] == "Rembrosoft-Main-PC"
    events = client.get("/api/tasks/REM-001/events").json()["items"]
    assert events[-1]["event_type"] == "task_started"


def test_progress_event(client, auth, task):
    before = task["last_activity_at"]
    response = client.post(
        "/api/tasks/REM-001/progress",
        json={"message": "Implemented table style parsing", "metadata": {"files": 3}},
        headers=auth,
    )
    assert response.status_code == 200
    assert response.json()["last_activity_at"] >= before
    events = client.get("/api/tasks/REM-001/events").json()["items"]
    progress = [e for e in events if e["event_type"] == "progress"]
    assert progress and progress[-1]["message"] == "Implemented table style parsing"
    assert progress[-1]["metadata"] == {"files": 3}


def test_progress_can_update_status(client, auth, task):
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    response = client.post(
        "/api/tasks/REM-001/progress",
        json={"message": "Need input", "status": "waiting_for_user"},
        headers=auth,
    )
    assert response.json()["status"] == "waiting_for_user"


def test_testing_updates(client, auth, task):
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    response = client.post(
        "/api/tasks/REM-001/testing",
        json={"kind": "tests", "status": "started"}, headers=auth,
    )
    body = response.json()
    assert body["tests_status"] == "running"
    assert body["status"] == "testing"
    response = client.post(
        "/api/tasks/REM-001/testing",
        json={"kind": "tests", "status": "passed", "message": "42 tests passed"}, headers=auth,
    )
    assert response.json()["tests_status"] == "passed"
    response = client.post(
        "/api/tasks/REM-001/testing",
        json={"kind": "build", "status": "failed"}, headers=auth,
    )
    assert response.json()["build_status"] == "failed"
    events = [e["event_type"] for e in client.get("/api/tasks/REM-001/events").json()["items"]]
    assert "tests_started" in events
    assert "tests_finished" in events
    assert "build_finished" in events
    response = client.post(
        "/api/tasks/REM-001/testing",
        json={"kind": "tests", "status": "bogus"}, headers=auth,
    )
    assert response.status_code == 422


def test_finish_results_in_needs_review(client, auth, task):
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    response = client.post(
        "/api/tasks/REM-001/finish",
        json={"summary": "Implemented DOCX fixes.", "branch": "agent/rem-001-docx",
              "commit": "a94c2e1", "tests": "passed", "build": "passed", "exit_code": 0},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "needs_review"  # never directly 'completed'
    assert body["result_summary"] == "Implemented DOCX fixes."
    assert body["end_commit"] == "a94c2e1"
    assert body["finished_at"] is not None
    events = [e["event_type"] for e in client.get("/api/tasks/REM-001/events").json()["items"]]
    assert "agent_finished" in events
    assert "review_requested" in events


def test_fail_task(client, auth, task):
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    response = client.post(
        "/api/tasks/REM-001/fail",
        json={"error": "Fixture missing.", "tests": "failed", "build": "not_run", "exit_code": 1},
        headers=auth,
    )
    body = response.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "Fixture missing."
    assert body["tests_status"] == "failed"
    assert body["build_status"] == "not_run"
    assert body["exit_code"] == 1
    events = [e["event_type"] for e in client.get("/api/tasks/REM-001/events").json()["items"]]
    assert "agent_failed" in events


def test_block_requires_reason(client, auth, task):
    assert client.post("/api/tasks/REM-001/block", json={}, headers=auth).status_code == 422
    response = client.post(
        "/api/tasks/REM-001/block", json={"reason": "Missing test document."}, headers=auth
    )
    assert response.json()["status"] == "blocked"


def test_approve_flow(client, auth, task):
    # Approve only allowed from needs_review / waiting_for_approval
    assert client.post("/api/tasks/REM-001/approve", json={}, headers=auth).status_code == 409
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    client.post("/api/tasks/REM-001/finish", json={"summary": "Done."}, headers=auth)
    response = client.post(
        "/api/tasks/REM-001/approve", json={"review_note": "Nice work"}, headers=auth
    )
    body = response.json()
    assert body["status"] == "completed"
    assert body["approved_at"] is not None
    assert body["review_note"] == "Nice work"
    events = [e["event_type"] for e in client.get("/api/tasks/REM-001/events").json()["items"]]
    assert "task_approved" in events


def test_reject_requires_note(client, auth, task):
    client.post("/api/tasks/REM-001/start", json={}, headers=auth)
    client.post("/api/tasks/REM-001/finish", json={"summary": "Done."}, headers=auth)
    assert client.post("/api/tasks/REM-001/reject", json={}, headers=auth).status_code == 422
    assert client.post(
        "/api/tasks/REM-001/reject", json={"review_note": ""}, headers=auth
    ).status_code == 422
    response = client.post(
        "/api/tasks/REM-001/reject", json={"review_note": "Tables still broken."}, headers=auth
    )
    body = response.json()
    assert body["status"] == "rejected"
    assert body["rejected_at"] is not None
    assert body["review_note"] == "Tables still broken."


def test_archive(client, auth, task):
    response = client.post("/api/tasks/REM-001/archive", headers=auth)
    assert response.json()["is_archived"] is True
    # Archived tasks are hidden by default in listing
    assert client.get("/api/tasks").json()["total"] == 0
    assert client.get("/api/tasks", params={"is_archived": True}).json()["total"] == 1


def test_cancel(client, auth, task):
    response = client.post("/api/tasks/REM-001/cancel", json={"reason": "Not needed"}, headers=auth)
    assert response.json()["status"] == "cancelled"
    # Terminal task rejects further lifecycle calls
    assert client.post("/api/tasks/REM-001/start", json={}, headers=auth).status_code == 409
    assert client.post(
        "/api/tasks/REM-001/finish", json={"summary": "x"}, headers=auth
    ).status_code == 409


def test_custom_event(client, auth, task):
    response = client.post(
        "/api/tasks/REM-001/events",
        json={"event_type": "command_started", "message": "pytest", "metadata": {"cwd": "backend"}},
        headers=auth,
    )
    assert response.status_code == 201
    assert response.json()["event_type"] == "command_started"
    assert client.post(
        "/api/tasks/REM-001/events", json={"event_type": "  "}, headers=auth
    ).status_code == 422
