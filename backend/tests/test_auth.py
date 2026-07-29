def test_write_requires_token(client):
    response = client.post("/api/projects", json={"name": "NoAuth"})
    assert response.status_code == 401


def test_write_rejects_wrong_token(client):
    response = client.post(
        "/api/projects", json={"name": "NoAuth"},
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


def test_write_accepts_valid_token(client, auth):
    response = client.post("/api/projects", json={"name": "WithAuth"}, headers=auth)
    assert response.status_code == 201


def test_read_does_not_require_token(client, project):
    assert client.get("/api/projects").status_code == 200
    assert client.get("/api/tasks").status_code == 200
    assert client.get("/api/workers").status_code == 200
    assert client.get("/api/dashboard/summary").status_code == 200
