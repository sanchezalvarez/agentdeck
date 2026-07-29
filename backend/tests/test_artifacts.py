def test_artifact_requires_path_or_url(client, auth, task):
    response = client.post(
        "/api/tasks/REM-001/artifacts",
        json={"artifact_type": "screenshot", "name": "Preview"},
        headers=auth,
    )
    assert response.status_code == 422


def test_artifact_crud(client, auth, task):
    response = client.post(
        "/api/tasks/REM-001/artifacts",
        json={"artifact_type": "screenshot", "name": "Preview",
              "local_path": "D:\\AgentWorkspaces\\artifacts\\preview.png"},
        headers=auth,
    )
    assert response.status_code == 201
    artifact = response.json()
    assert artifact["artifact_type"] == "screenshot"

    listing = client.get("/api/tasks/REM-001/artifacts").json()
    assert len(listing) == 1

    events = [e["event_type"] for e in client.get("/api/tasks/REM-001/events").json()["items"]]
    assert "artifact_added" in events

    response = client.delete(f"/api/tasks/REM-001/artifacts/{artifact['id']}", headers=auth)
    assert response.status_code == 204
    assert client.get("/api/tasks/REM-001/artifacts").json() == []


def test_invalid_artifact_type(client, auth, task):
    response = client.post(
        "/api/tasks/REM-001/artifacts",
        json={"artifact_type": "virus", "name": "X", "url": "http://localhost/x"},
        headers=auth,
    )
    assert response.status_code == 422


def test_delete_artifact_wrong_task(client, auth, project, task):
    client.post("/api/tasks", json={"title": "Other", "project": "crowforge"}, headers=auth)
    artifact = client.post(
        "/api/tasks/REM-001/artifacts",
        json={"artifact_type": "log", "name": "Log", "url": "http://localhost/log"},
        headers=auth,
    ).json()
    response = client.delete(f"/api/tasks/REM-002/artifacts/{artifact['id']}", headers=auth)
    assert response.status_code == 404
