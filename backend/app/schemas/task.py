from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from ..models.enums import (
    AgentType,
    ArtifactType,
    CheckStatus,
    TaskPriority,
    TaskStatus,
)
from .project import ProjectRead
from .worker import WorkerRead


class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    project: str | int | None = None  # project slug or numeric id
    agent_type: AgentType | None = None
    priority: TaskPriority = TaskPriority.normal
    requested_by: str | None = None
    discord_guild_id: str | None = None
    discord_channel_id: str | None = None
    discord_thread_id: str | None = None
    branch: str | None = None
    working_directory: str | None = None

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("title must not be empty")
        return v


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    project: str | int | None = None
    agent_type: AgentType | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    requested_by: str | None = None
    discord_guild_id: str | None = None
    discord_channel_id: str | None = None
    discord_thread_id: str | None = None
    branch: str | None = None
    working_directory: str | None = None
    worktree_path: str | None = None
    is_archived: bool | None = None


class TaskStartPayload(BaseModel):
    agent_type: AgentType | None = None
    project: str | int | None = None
    worker: str | None = None
    process_id: int | None = None
    session_id: str | None = None
    working_directory: str | None = None
    branch: str | None = None
    worktree_path: str | None = None
    start_commit: str | None = None
    message: str | None = None


class TaskProgressPayload(BaseModel):
    message: str
    status: TaskStatus | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message must not be empty")
        return v


class TaskTestingPayload(BaseModel):
    kind: str  # tests | build
    status: str  # started | running | passed | failed | not_run
    message: str | None = None

    @field_validator("kind")
    @classmethod
    def kind_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"tests", "build"}:
            raise ValueError("kind must be 'tests' or 'build'")
        return v

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in {"started", "running", "passed", "failed", "not_run"}:
            raise ValueError("status must be one of: started, running, passed, failed, not_run")
        return v


class TaskFinishPayload(BaseModel):
    summary: str
    branch: str | None = None
    commit: str | None = None
    start_commit: str | None = None
    tests: CheckStatus | None = None
    build: CheckStatus | None = None
    exit_code: int | None = None

    @field_validator("summary")
    @classmethod
    def summary_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("summary must not be empty")
        return v


class TaskFailPayload(BaseModel):
    error: str
    tests: CheckStatus | None = None
    build: CheckStatus | None = None
    exit_code: int | None = None

    @field_validator("error")
    @classmethod
    def error_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("error must not be empty")
        return v


class TaskBlockPayload(BaseModel):
    reason: str

    @field_validator("reason")
    @classmethod
    def reason_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("reason must not be empty")
        return v


class TaskCancelPayload(BaseModel):
    reason: str | None = None


class TaskApprovePayload(BaseModel):
    review_note: str | None = None


class TaskRejectPayload(BaseModel):
    review_note: str

    @field_validator("review_note")
    @classmethod
    def note_not_empty(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3:
            raise ValueError("review_note is required when rejecting a task")
        return v


class TaskEventCreate(BaseModel):
    event_type: str
    message: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("event_type")
    @classmethod
    def event_type_valid(cls, v: str) -> str:
        v = v.strip()
        if not v or len(v) > 100:
            raise ValueError("event_type must be a non-empty string (max 100 chars)")
        return v


class TaskEventRead(BaseModel):
    id: int
    task_id: int
    event_type: str
    message: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class ArtifactCreate(BaseModel):
    artifact_type: ArtifactType = ArtifactType.other
    name: str
    local_path: str | None = None
    url: str | None = None
    metadata: dict[str, Any] | None = None

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @model_validator(mode="after")
    def path_or_url_required(self) -> "ArtifactCreate":
        if not self.local_path and not self.url:
            raise ValueError("at least one of local_path or url must be provided")
        return self


class ArtifactRead(BaseModel):
    id: int
    task_id: int
    artifact_type: ArtifactType
    name: str
    local_path: str | None
    url: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    public_id: str
    title: str
    description: str | None
    project_id: int | None
    agent_type: AgentType | None
    status: TaskStatus
    priority: TaskPriority
    discord_guild_id: str | None
    discord_channel_id: str | None
    discord_thread_id: str | None
    requested_by: str | None
    worker_id: int | None
    process_id: int | None
    session_id: str | None
    working_directory: str | None
    branch: str | None
    worktree_path: str | None
    start_commit: str | None
    end_commit: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    last_activity_at: datetime
    result_summary: str | None
    error_message: str | None
    tests_status: CheckStatus
    build_status: CheckStatus
    exit_code: int | None
    is_archived: bool
    approved_at: datetime | None
    rejected_at: datetime | None
    review_note: str | None
    project: ProjectRead | None = None
    worker: WorkerRead | None = None


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int


class TaskEventListResponse(BaseModel):
    items: list[TaskEventRead]
    total: int
    limit: int
    offset: int
