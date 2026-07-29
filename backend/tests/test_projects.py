def test_create_project(client, auth):
    response = client.post(
        "/api/projects",
        json={"name": "Unity Game", "project_type": "unity"},
        headers=auth,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == "unity-game"  # auto-generated from name
    assert body["project_type"] == "unity"
    assert body["default_branch"] == "main"
    assert body["is_active"] is True


def test_duplicate_slug_rejected(client, auth, project):
    response = client.post(
        "/api/projects", json={"name": "Other", "slug": "crowforge"}, headers=auth
    )
    assert response.status_code == 409


def test_invalid_slug_rejected(client, auth):
    response = client.post(
        "/api/projects", json={"name": "X", "slug": "Bad Slug!"}, headers=auth
    )
    assert response.status_code == 422


def test_filter_active_projects(client, auth, project):
    client.post("/api/projects", json={"name": "Old", "is_active": False}, headers=auth)
    active = client.get("/api/projects", params={"active": True}).json()
    assert [p["slug"] for p in active] == ["crowforge"]
    everything = client.get("/api/projects").json()
    assert len(everything) == 2


def test_patch_project(client, auth, project):
    response = client.patch(
        f"/api/projects/{project['id']}",
        json={"default_branch": "develop", "is_active": False},
        headers=auth,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["default_branch"] == "develop"
    assert body["is_active"] is False
