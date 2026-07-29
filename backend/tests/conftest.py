import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings
from app.database import get_session
from app.main import create_app

TEST_TOKEN = "test-write-token"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def client(engine, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "write_token", TEST_TOKEN)
    # Settings are read from the real .env, so without this every test that
    # finishes, fails or blocks a task would post to the developer's actual
    # Discord channel. Tests that exercise the webhook opt back in explicitly.
    monkeypatch.setattr(settings, "discord_summary_webhook", "")

    def override_get_session():
        with Session(engine) as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth():
    return {"Authorization": f"Bearer {TEST_TOKEN}"}


@pytest.fixture
def project(client, auth):
    response = client.post(
        "/api/projects",
        json={"name": "CrowForge", "slug": "crowforge", "project_type": "desktop",
              "repository_path": "D:\\Projects\\CrowForge"},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def task(client, auth, project):
    response = client.post(
        "/api/tasks",
        json={"title": "Fix DOCX table import", "description": "Borders are lost.",
              "project": "crowforge", "agent_type": "claude", "requested_by": "Lubomir"},
        headers=auth,
    )
    assert response.status_code == 201, response.text
    return response.json()
