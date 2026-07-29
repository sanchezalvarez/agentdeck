import json
from datetime import datetime, timedelta
from typing import Any

from ..config import get_settings
from ..models import Artifact, Task, TaskEvent, Worker, WorkerStatus
from ..schemas.task import ArtifactRead, TaskEventRead, TaskRead
from ..schemas.worker import WorkerRead
from ..utils.time import utcnow


def parse_metadata(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {"value": value}
    except json.JSONDecodeError:
        return {"raw": raw}


def worker_to_read(worker: Worker) -> WorkerRead:
    data = WorkerRead.model_validate(worker)
    stale_after = timedelta(seconds=get_settings().worker_stale_seconds)
    if worker.last_seen_at is None:
        data.is_stale = True
        data.effective_status = WorkerStatus.unknown
    elif utcnow() - worker.last_seen_at > stale_after:
        data.is_stale = True
        data.effective_status = WorkerStatus.offline
    else:
        data.is_stale = False
        data.effective_status = worker.status
    return data


def task_to_read(task: Task) -> TaskRead:
    data = TaskRead.model_validate(task)
    if task.worker is not None:
        data.worker = worker_to_read(task.worker)
    return data


def event_to_read(event: TaskEvent) -> TaskEventRead:
    return TaskEventRead(
        id=event.id,
        task_id=event.task_id,
        event_type=event.event_type,
        message=event.message,
        metadata=parse_metadata(event.metadata_json),
        created_at=event.created_at,
    )


def artifact_to_read(artifact: Artifact) -> ArtifactRead:
    return ArtifactRead(
        id=artifact.id,
        task_id=artifact.task_id,
        artifact_type=artifact.artifact_type,
        name=artifact.name,
        local_path=artifact.local_path,
        url=artifact.url,
        metadata=parse_metadata(artifact.metadata_json),
        created_at=artifact.created_at,
    )


def task_sse_payload(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "public_id": task.public_id,
        "title": task.title,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "project_id": task.project_id,
        "last_activity_at": task.last_activity_at.isoformat() if task.last_activity_at else None,
    }


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None
