from datetime import timedelta

from sqlmodel import Session, select

from app.models import Worker
from app.utils.time import utcnow


def test_heartbeat_creates_and_updates_worker(client, auth):
    response = client.post(
        "/api/workers/heartbeat",
        json={"worker": "Rembrosoft-Main-PC", "hostname": "REMBRO-MAIN",
              "operating_system": "Windows 11", "claude_available": True,
              "codex_available": True, "unity_available": True, "unity_mcp_available": False},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "online"
    assert body["effective_status"] == "online"
    assert body["is_stale"] is False
    assert body["claude_available"] is True
    assert body["unity_mcp_available"] is False

    # Partial update keeps previous capability flags
    response = client.post(
        "/api/workers/heartbeat",
        json={"worker": "Rembrosoft-Main-PC", "unity_mcp_available": True},
        headers=auth,
    )
    body = response.json()
    assert body["claude_available"] is True
    assert body["unity_mcp_available"] is True
    assert len(client.get("/api/workers").json()) == 1


def test_heartbeat_requires_token(client):
    assert client.post("/api/workers/heartbeat", json={"worker": "X"}).status_code == 401


def test_stale_worker_reported_offline(client, auth, engine):
    client.post("/api/workers/heartbeat", json={"worker": "Old-PC"}, headers=auth)
    with Session(engine) as session:
        worker = session.exec(select(Worker).where(Worker.name == "Old-PC")).one()
        worker.last_seen_at = utcnow() - timedelta(hours=2)
        session.add(worker)
        session.commit()
        worker_id = worker.id
    body = client.get(f"/api/workers/{worker_id}").json()
    assert body["status"] == "online"
    assert body["effective_status"] == "offline"
    assert body["is_stale"] is True
