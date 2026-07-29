import pytest


@pytest.fixture
def many_tasks(client, auth, project):
    client.post("/api/projects", json={"name": "Rembrosoft Web", "slug": "rembrosoft-web"}, headers=auth)
    specs = [
        {"title": "Fix DOCX import", "project": "crowforge", "agent_type": "claude",
         "priority": "high", "requested_by": "Lubomir"},
        {"title": "Add sitemap", "project": "rembrosoft-web", "agent_type": "codex",
         "priority": "low", "requested_by": "Lubomir"},
        {"title": "Update hero section", "project": "rembrosoft-web", "agent_type": "claude",
         "priority": "normal", "requested_by": "Peter"},
    ]
    created = []
    for spec in specs:
        created.append(client.post("/api/tasks", json=spec, headers=auth).json())
    # Move one task to failed
    client.post(f"/api/tasks/{created[1]['public_id']}/start", json={}, headers=auth)
    client.post(f"/api/tasks/{created[1]['public_id']}/fail", json={"error": "boom"}, headers=auth)
    return created


def test_filter_by_project(client, many_tasks):
    body = client.get("/api/tasks", params={"project": "rembrosoft-web"}).json()
    assert body["total"] == 2


def test_filter_by_agent_and_priority(client, many_tasks):
    assert client.get("/api/tasks", params={"agent_type": "claude"}).json()["total"] == 2
    assert client.get("/api/tasks", params={"priority": "high"}).json()["total"] == 1


def test_filter_by_status(client, many_tasks):
    body = client.get("/api/tasks", params={"status": "failed"}).json()
    assert body["total"] == 1
    assert body["items"][0]["public_id"] == "REM-002"


def test_filter_by_requested_by(client, many_tasks):
    assert client.get("/api/tasks", params={"requested_by": "Peter"}).json()["total"] == 1


def test_search(client, many_tasks):
    assert client.get("/api/tasks", params={"search": "docx"}).json()["total"] == 1
    assert client.get("/api/tasks", params={"search": "REM-003"}).json()["total"] == 1


def test_date_filters(client, many_tasks):
    assert client.get("/api/tasks", params={"created_from": "2000-01-01"}).json()["total"] == 3
    assert client.get("/api/tasks", params={"created_to": "2000-01-01"}).json()["total"] == 0
    assert client.get("/api/tasks", params={"created_from": "not-a-date"}).status_code == 422


def test_pagination(client, many_tasks):
    body = client.get("/api/tasks", params={"limit": 2, "offset": 0}).json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    rest = client.get("/api/tasks", params={"limit": 2, "offset": 2}).json()
    assert len(rest["items"]) == 1
