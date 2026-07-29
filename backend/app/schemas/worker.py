from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from ..models.enums import WorkerStatus


class WorkerHeartbeat(BaseModel):
    worker: str
    hostname: str | None = None
    operating_system: str | None = None
    status: WorkerStatus = WorkerStatus.online
    claude_available: bool | None = None
    codex_available: bool | None = None
    unity_available: bool | None = None
    unity_mcp_available: bool | None = None

    @field_validator("worker")
    @classmethod
    def worker_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("worker name must not be empty")
        return v


class WorkerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    hostname: str | None
    operating_system: str | None
    status: WorkerStatus
    last_seen_at: datetime | None
    claude_available: bool
    codex_available: bool
    unity_available: bool
    unity_mcp_available: bool
    created_at: datetime
    updated_at: datetime
    # Computed: reported status considering heartbeat staleness.
    effective_status: WorkerStatus | None = None
    is_stale: bool = False
