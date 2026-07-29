import json
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlmodel import col, func, or_, select

from ..dependencies import SessionDep, WriteAuth
from ..models import (
    AgentType,
    Artifact,
    Project,
    Task,
    TaskEvent,
    TaskPriority,
    TaskStatus,
)
from ..schemas.task import (
    ArtifactCreate,
    ArtifactRead,
    TaskApprovePayload,
    TaskBlockPayload,
    TaskCancelPayload,
    TaskCreate,
    TaskEventCreate,
    TaskEventListResponse,
    TaskEventRead,
    TaskFailPayload,
    TaskFinishPayload,
    TaskListResponse,
    TaskProgressPayload,
    TaskRead,
    TaskRejectPayload,
    TaskStartPayload,
    TaskTestingPayload,
    TaskUpdate,
)
from ..services import task_service
from ..services.serializers import artifact_to_read, event_to_read, task_to_read
from ..utils.time import utcnow

router = APIRouter(prefix="/tasks", tags=["tasks"])


def _parse_date(value: str | None, name: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid datetime for '{name}': {value}") from exc


@router.post("", response_model=TaskRead, status_code=201, dependencies=[WriteAuth])
async def create_task(payload: TaskCreate, session: SessionDep) -> TaskRead:
    task = task_service.create_task(session, payload)
    return task_to_read(task)


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    session: SessionDep,
    project: str | None = None,
    agent_type: AgentType | None = None,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    requested_by: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    is_archived: bool | None = False,
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> TaskListResponse:
    query = select(Task)
    if project:
        proj = task_service.resolve_project(session, project)
        query = query.where(Task.project_id == proj.id)
    if agent_type is not None:
        query = query.where(Task.agent_type == agent_type)
    if status is not None:
        query = query.where(Task.status == status)
    if priority is not None:
        query = query.where(Task.priority == priority)
    if requested_by:
        query = query.where(Task.requested_by == requested_by)
    date_from = _parse_date(created_from, "created_from")
    if date_from is not None:
        query = query.where(Task.created_at >= date_from)
    date_to = _parse_date(created_to, "created_to")
    if date_to is not None:
        # A bare date means "up to and including that day".
        if created_to and len(created_to.strip()) == 10:
            date_to = date_to + timedelta(days=1)
        query = query.where(Task.created_at < date_to)
    if is_archived is not None:
        query = query.where(Task.is_archived == is_archived)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                col(Task.public_id).ilike(pattern),
                col(Task.title).ilike(pattern),
                col(Task.description).ilike(pattern),
            )
        )
    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    if isinstance(total, tuple):
        total = total[0]
    rows = session.exec(
        query.order_by(col(Task.created_at).desc()).limit(limit).offset(offset)
    ).all()
    return TaskListResponse(
        items=[task_to_read(t) for t in rows], total=int(total), limit=limit, offset=offset
    )


@router.get("/{task_identifier}", response_model=TaskRead)
async def get_task(task_identifier: str, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task)


@router.patch("/{task_identifier}", response_model=TaskRead, dependencies=[WriteAuth])
async def update_task(task_identifier: str, payload: TaskUpdate, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    data = payload.model_dump(exclude_unset=True)
    if "project" in data:
        project_ref = data.pop("project")
        if project_ref is None:
            task.project_id = None
        else:
            proj = task_service.resolve_project(session, project_ref)
            task.project_id = proj.id
    for key, value in data.items():
        setattr(task, key, value)
    task.last_activity_at = utcnow()
    session.add(task)
    session.commit()
    session.refresh(task)
    task_service.publish_task_event("task_status_changed", task)
    return task_to_read(task)


# --- Lifecycle -------------------------------------------------------------


@router.post("/{task_identifier}/start", response_model=TaskRead, dependencies=[WriteAuth])
async def start_task(task_identifier: str, payload: TaskStartPayload, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.start_task(session, task, payload))


@router.post("/{task_identifier}/progress", response_model=TaskRead, dependencies=[WriteAuth])
async def progress_task(
    task_identifier: str, payload: TaskProgressPayload, session: SessionDep
) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    task_service.ensure_not_terminal(task, "report progress on")
    event_type = "progress"
    if payload.status is not None:
        task.status = payload.status
        if payload.status == TaskStatus.waiting_for_user:
            event_type = "waiting_for_user"
        elif payload.status == TaskStatus.waiting_for_approval:
            event_type = "waiting_for_approval"
    session.add(task)
    task_service.add_event(session, task, event_type, payload.message, payload.metadata)
    session.commit()
    session.refresh(task)
    task_service.publish_task_event("task_progress", task, {"message": payload.message})
    return task_to_read(task)


@router.post("/{task_identifier}/testing", response_model=TaskRead, dependencies=[WriteAuth])
async def testing_task(
    task_identifier: str, payload: TaskTestingPayload, session: SessionDep
) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.testing_task(session, task, payload))


@router.post("/{task_identifier}/finish", response_model=TaskRead, dependencies=[WriteAuth])
async def finish_task(task_identifier: str, payload: TaskFinishPayload, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.finish_task(session, task, payload))


@router.post("/{task_identifier}/fail", response_model=TaskRead, dependencies=[WriteAuth])
async def fail_task(task_identifier: str, payload: TaskFailPayload, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.fail_task(session, task, payload))


@router.post("/{task_identifier}/block", response_model=TaskRead, dependencies=[WriteAuth])
async def block_task(task_identifier: str, payload: TaskBlockPayload, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.block_task(session, task, payload.reason))


@router.post("/{task_identifier}/cancel", response_model=TaskRead, dependencies=[WriteAuth])
async def cancel_task(
    task_identifier: str, session: SessionDep, payload: TaskCancelPayload | None = None
) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    reason = payload.reason if payload else None
    return task_to_read(task_service.cancel_task(session, task, reason))


@router.post("/{task_identifier}/approve", response_model=TaskRead, dependencies=[WriteAuth])
async def approve_task(
    task_identifier: str, session: SessionDep, payload: TaskApprovePayload | None = None
) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    note = payload.review_note if payload else None
    return task_to_read(task_service.approve_task(session, task, note))


@router.post("/{task_identifier}/reject", response_model=TaskRead, dependencies=[WriteAuth])
async def reject_task(task_identifier: str, payload: TaskRejectPayload, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.reject_task(session, task, payload.review_note))


@router.post("/{task_identifier}/archive", response_model=TaskRead, dependencies=[WriteAuth])
async def archive_task(task_identifier: str, session: SessionDep) -> TaskRead:
    task = task_service.resolve_task(session, task_identifier)
    return task_to_read(task_service.archive_task(session, task))


# --- Events ----------------------------------------------------------------


@router.get("/{task_identifier}/events", response_model=TaskEventListResponse)
async def list_events(
    task_identifier: str,
    session: SessionDep,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
) -> TaskEventListResponse:
    task = task_service.resolve_task(session, task_identifier)
    base = select(TaskEvent).where(TaskEvent.task_id == task.id)
    total = session.exec(select(func.count()).select_from(base.subquery())).one()
    if isinstance(total, tuple):
        total = total[0]
    order_col = col(TaskEvent.id).asc() if order == "asc" else col(TaskEvent.id).desc()
    events = session.exec(base.order_by(order_col).limit(limit).offset(offset)).all()
    return TaskEventListResponse(
        items=[event_to_read(e) for e in events], total=int(total), limit=limit, offset=offset
    )


@router.post(
    "/{task_identifier}/events",
    response_model=TaskEventRead,
    status_code=201,
    dependencies=[WriteAuth],
)
async def create_event(
    task_identifier: str, payload: TaskEventCreate, session: SessionDep
) -> TaskEventRead:
    task = task_service.resolve_task(session, task_identifier)
    event = task_service.add_event(
        session, task, payload.event_type, payload.message, payload.metadata
    )
    session.commit()
    session.refresh(event)
    session.refresh(task)
    task_service.publish_task_event(
        "task_progress", task, {"event_type": payload.event_type, "message": payload.message}
    )
    return event_to_read(event)


# --- Artifacts -------------------------------------------------------------


@router.get("/{task_identifier}/artifacts", response_model=list[ArtifactRead])
async def list_artifacts(task_identifier: str, session: SessionDep) -> list[ArtifactRead]:
    task = task_service.resolve_task(session, task_identifier)
    artifacts = session.exec(
        select(Artifact).where(Artifact.task_id == task.id).order_by(col(Artifact.id).asc())
    ).all()
    return [artifact_to_read(a) for a in artifacts]


@router.post(
    "/{task_identifier}/artifacts",
    response_model=ArtifactRead,
    status_code=201,
    dependencies=[WriteAuth],
)
async def create_artifact(
    task_identifier: str, payload: ArtifactCreate, session: SessionDep
) -> ArtifactRead:
    task = task_service.resolve_task(session, task_identifier)
    artifact = Artifact(
        task_id=task.id,
        artifact_type=payload.artifact_type,
        name=payload.name,
        local_path=payload.local_path,
        url=payload.url,
        metadata_json=json.dumps(payload.metadata, default=str) if payload.metadata else None,
    )
    session.add(artifact)
    task_service.add_event(
        session, task, "artifact_added", f"Artifact added: {payload.name}",
        metadata={"artifact_type": payload.artifact_type.value},
    )
    session.commit()
    session.refresh(artifact)
    session.refresh(task)
    task_service.publish_task_event("task_progress", task, {"artifact": payload.name})
    return artifact_to_read(artifact)


@router.delete(
    "/{task_identifier}/artifacts/{artifact_id}", status_code=204, dependencies=[WriteAuth]
)
async def delete_artifact(task_identifier: str, artifact_id: int, session: SessionDep) -> None:
    task = task_service.resolve_task(session, task_identifier)
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or artifact.task_id != task.id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    # V1 removes only the database record — files on disk are never touched.
    session.delete(artifact)
    session.commit()
