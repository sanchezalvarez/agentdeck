from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel

from ..utils.time import utcnow
from .enums import (
    AgentType,
    ArtifactType,
    CheckStatus,
    ProjectType,
    TaskPriority,
    TaskStatus,
    WorkerStatus,
)


class Project(SQLModel, table=True):
    __tablename__ = "projects"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=200)
    slug: str = Field(unique=True, index=True, max_length=100)
    repository_path: str | None = Field(default=None, max_length=1024)
    default_branch: str = Field(default="main", max_length=200)
    project_type: ProjectType = Field(default=ProjectType.other, index=True)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    tasks: list["Task"] = Relationship(back_populates="project")


class Worker(SQLModel, table=True):
    __tablename__ = "workers"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True, max_length=200)
    hostname: str | None = Field(default=None, max_length=255)
    operating_system: str | None = Field(default=None, max_length=255)
    status: WorkerStatus = Field(default=WorkerStatus.unknown, index=True)
    last_seen_at: datetime | None = Field(default=None, index=True)
    claude_available: bool = Field(default=False)
    codex_available: bool = Field(default=False)
    unity_available: bool = Field(default=False)
    unity_mcp_available: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    tasks: list["Task"] = Relationship(back_populates="worker")


class Task(SQLModel, table=True):
    __tablename__ = "tasks"

    id: int | None = Field(default=None, primary_key=True)
    public_id: str = Field(unique=True, index=True, max_length=20)
    title: str = Field(max_length=500)
    description: str | None = Field(default=None)
    project_id: int | None = Field(default=None, foreign_key="projects.id", index=True)
    agent_type: AgentType | None = Field(default=None, index=True)
    status: TaskStatus = Field(default=TaskStatus.queued, index=True)
    priority: TaskPriority = Field(default=TaskPriority.normal, index=True)
    discord_guild_id: str | None = Field(default=None, max_length=64)
    discord_channel_id: str | None = Field(default=None, max_length=64)
    discord_thread_id: str | None = Field(default=None, max_length=64)
    requested_by: str | None = Field(default=None, index=True, max_length=200)
    worker_id: int | None = Field(default=None, foreign_key="workers.id", index=True)
    process_id: int | None = Field(default=None)
    session_id: str | None = Field(default=None, max_length=200)
    working_directory: str | None = Field(default=None, max_length=1024)
    branch: str | None = Field(default=None, max_length=300)
    worktree_path: str | None = Field(default=None, max_length=1024)
    start_commit: str | None = Field(default=None, max_length=64)
    end_commit: str | None = Field(default=None, max_length=64)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    last_activity_at: datetime = Field(default_factory=utcnow, index=True)
    result_summary: str | None = Field(default=None)
    error_message: str | None = Field(default=None)
    tests_status: CheckStatus = Field(default=CheckStatus.pending)
    build_status: CheckStatus = Field(default=CheckStatus.pending)
    exit_code: int | None = Field(default=None)
    is_archived: bool = Field(default=False, index=True)
    approved_at: datetime | None = Field(default=None)
    rejected_at: datetime | None = Field(default=None)
    review_note: str | None = Field(default=None)

    project: Project | None = Relationship(back_populates="tasks")
    worker: Worker | None = Relationship(back_populates="tasks")
    events: list["TaskEvent"] = Relationship(back_populates="task")
    artifacts: list["Artifact"] = Relationship(back_populates="task")


class TaskEvent(SQLModel, table=True):
    __tablename__ = "task_events"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    event_type: str = Field(index=True, max_length=100)
    message: str | None = Field(default=None)
    metadata_json: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow, index=True)

    task: Task = Relationship(back_populates="events")


class Artifact(SQLModel, table=True):
    __tablename__ = "artifacts"

    id: int | None = Field(default=None, primary_key=True)
    task_id: int = Field(foreign_key="tasks.id", index=True)
    artifact_type: ArtifactType = Field(default=ArtifactType.other, index=True)
    name: str = Field(max_length=300)
    local_path: str | None = Field(default=None, max_length=1024)
    url: str | None = Field(default=None, max_length=2048)
    metadata_json: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)

    task: Task = Relationship(back_populates="artifacts")
