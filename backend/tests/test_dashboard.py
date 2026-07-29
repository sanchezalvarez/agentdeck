def test_dashboard_summary(client, auth, project):
    for i in range(3):
        client.post("/api/tasks", json={"title": f"T{i}", "project": "crowforge"}, headers=auth)
    client.post("/api/tasks/REM-001/start", json={"worker": "Main-PC"}, headers=auth)
    client.post("/api/tasks/REM-002/start", json={}, headers=auth)
    client.post("/api/tasks/REM-002/finish", json={"summary": "Done"}, headers=auth)
    client.post("/api/tasks/REM-002/approve", json={}, headers=auth)
    client.post("/api/tasks/REM-003/start", json={}, headers=auth)
    client.post("/api/tasks/REM-003/fail", json={"error": "boom"}, headers=auth)

    body = client.get("/api/dashboard/summary").json()
    assert body["running_count"] == 1
    assert body["needs_review_count"] == 0
    assert body["completed_today_count"] == 1
    assert body["failed_today_count"] == 1
    assert len(body["active_tasks"]) == 1
    assert body["active_tasks"][0]["public_id"] == "REM-001"
    assert len(body["recent_failed_tasks"]) == 1
    assert body["workers"][0]["name"] == "Main-PC"
    crowforge = [p for p in body["projects"] if p["project"]["slug"] == "crowforge"][0]
    assert crowforge["running_tasks"] == 1
    assert crowforge["failed_tasks"] == 1
    assert crowforge["last_completed_task_id"] == "REM-002"
