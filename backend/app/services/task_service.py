import json
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Integer, cast, func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..models import (
    ACTIVE_TASK_STATUSES,
    TERMINAL_TASK_STATUSES,
    CheckStatus,
    Project,
    Task,
    TaskEvent,
    TaskStatus,
    Worker,
    WorkerStatus,
)
from ..schemas.task import (
    TaskCreate,
    TaskFailPayload,
    TaskFinishPayload,
    TaskStartPayload,
    TaskTestingPayload,
)
from ..utils.time import utcnow
from . import discord_notify
from .broadcaster import broadcaster
from .serializers import task_sse_payload

PUBLIC_ID_RE = re.compile(r"^rem-(\d+)$", re.IGNORECASE)


def resolve_project(session: Session, ref: str | int | None) -> Project | None:
    """Resolve a project by numeric id or slug. Raises 404 when not found."""
    if ref is None:
        return None
    project: Project | None = None
    if isinstance(ref, int) or (isinstance(ref, str) and ref.isdigit()):
        project = session.get(Project, int(ref))
    if project is None and isinstance(ref, str):
        project = session.exec(select(Project).where(Project.slug == ref.lower())).first()
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project '{ref}' not found")
    return project


def resolve_task(session: Session, identifier: str) -> Task:
    """Resolve a task by numeric id or public id (REM-###)."""
    task: Task | None = None
    match = PUBLIC_ID_RE.match(identifier.strip())
    if match:
        public_id = f"REM-{int(match.group(1)):03d}"
        task = session.exec(select(Task).where(Task.public_id == public_id)).first()
        if task is None:
            # Also try the raw form in case IDs ever exceed 3 digits without padding.
            task = session.exec(
                select(Task).where(func.upper(Task.public_id) == identifier.strip().upper())
            ).first()
    elif identifier.isdigit():
        task = session.get(Task, int(identifier))
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task '{identifier}' not found")
    return task


def resolve_worker_by_name(session: Session, name: str | None) -> Worker | None:
    if not name:
        return None
    name = name.strip()
    worker = session.exec(select(Worker).where(Worker.name == name)).first()
    if worker is None:
        worker = Worker(name=name, status=WorkerStatus.unknown)
        session.add(worker)
        session.flush()
    return worker


def next_public_id(session: Session) -> str:
    max_num = session.exec(
        select(func.max(cast(func.substr(Task.public_id, 5), Integer)))
    ).one()
    if isinstance(max_num, tuple):
        max_num = max_num[0]
    next_num = (max_num or 0) + 1
    return f"REM-{next_num:03d}"


def add_event(
    session: Session,
    task: Task,
    event_type: str,
    message: str | None = None,
    metadata: dict[str, Any] | None = None,
    *,
    touch_activity: bool = True,
) -> TaskEvent:
    event = TaskEvent(
        task_id=task.id,
        event_type=event_type,
        message=message,
        metadata_json=json.dumps(metadata, default=str) if metadata else None,
        created_at=utcnow(),
    )
    session.add(event)
    if touch_activity:
        task.last_activity_at = utcnow()
        session.add(task)
    return event


def publish_task_event(event_type: str, task: Task, extra: dict[str, Any] | None = None) -> None:
    payload = task_sse_payload(task)
    if extra:
        payload.update(extra)
    broadcaster.publish(event_type, payload)


def create_task(session: Session, payload: TaskCreate) -> Task:
    project = resolve_project(session, payload.project)
    last_error: IntegrityError | None = None
    for _ in range(3):
        task = Task(
            public_id=next_public_id(session),
            title=payload.title,
            description=payload.description,
            project_id=project.id if project else None,
            agent_type=payload.agent_type,
            priority=payload.priority,
            requested_by=payload.requested_by,
            discord_guild_id=payload.discord_guild_id,
            discord_channel_id=payload.discord_channel_id,
            discord_thread_id=payload.discord_thread_id,
            branch=payload.branch,
            working_directory=payload.working_directory,
            status=TaskStatus.queued,
        )
        session.add(task)
        try:
            session.flush()
        except IntegrityError as exc:
            session.rollback()
            last_error = exc
            continue
        add_event(session, task, "task_created", f"Task created: {task.title}")
        session.commit()
        session.refresh(task)
        publish_task_event("task_created", task)
        return task
    raise HTTPException(status_code=500, detail="Could not allocate a unique task ID") from last_error


def ensure_not_terminal(task: Task, action: str) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot {action} task {task.public_id}: status is '{task.status.value}'",
        )


def start_task(session: Session, task: Task, payload: TaskStartPayload) -> Task:
    ensure_not_terminal(task, "start")
    now = utcnow()
    task.status = TaskStatus.running
    if task.started_at is None:
        task.started_at = now
    if payload.agent_type is not None:
        task.agent_type = payload.agent_type
    if payload.project is not None:
        project = resolve_project(session, payload.project)
        task.project_id = project.id if project else task.project_id
    worker = resolve_worker_by_name(session, payload.worker)
    if worker is not None:
        task.worker_id = worker.id
    for field in ("process_id", "session_id", "working_directory", "branch", "worktree_path", "start_commit"):
        value = getattr(payload, field)
        if value is not None:
            setattr(task, field, value)
    session.add(task)
    add_event(
        session,
        task,
        "task_started",
        payload.message or f"Agent started working on {task.public_id}",
        metadata={"agent_type": payload.agent_type.value if payload.agent_type else None,
                  "worker": payload.worker, "branch": payload.branch} if any(
            [payload.agent_type, payload.worker, payload.branch]) else None,
    )
    session.commit()
    session.refresh(task)
    publish_task_event("task_status_changed", task)
    return task


def testing_task(session: Session, task: Task, payload: TaskTestingPayload) -> Task:
    ensure_not_terminal(task, "update testing state of")
    status_map = {
        "started": CheckStatus.running,
        "running": CheckStatus.running,
        "passed": CheckStatus.passed,
        "failed": CheckStatus.failed,
        "not_run": CheckStatus.not_run,
    }
    check_status = status_map[payload.status]
    if payload.kind == "tests":
        task.tests_status = check_status
        event_type = "tests_started" if check_status == CheckStatus.running else "tests_finished"
    else:
        task.build_status = check_status
        event_type = "build_started" if check_status == CheckStatus.running else "build_finished"
    if check_status == CheckStatus.running and task.status == TaskStatus.running:
        task.status = TaskStatus.testing
    session.add(task)
    default_message = f"{payload.kind} {payload.status}"
    add_event(session, task, event_type, payload.message or default_message,
              metadata={"kind": payload.kind, "status": payload.status})
    session.commit()
    session.refresh(task)
    publish_task_event("task_status_changed", task)
    return task


def finish_task(session: Session, task: Task, payload: TaskFinishPayload) -> Task:
    ensure_not_terminal(task, "finish")
    now = utcnow()
    task.status = TaskStatus.needs_review
    task.result_summary = payload.summary
    if payload.branch is not None:
        task.branch = payload.branch
    if payload.commit is not None:
        task.end_commit = payload.commit
    if payload.start_commit is not None:
        task.start_commit = payload.start_commit
    if payload.tests is not None:
        task.tests_status = payload.tests
    if payload.build is not None:
        task.build_status = payload.build
    if payload.exit_code is not None:
        task.exit_code = payload.exit_code
    task.finished_at = now
    session.add(task)
    add_event(session, task, "agent_finished", payload.summary)
    add_event(session, task, "review_requested", f"{task.public_id} is ready for review")
    session.commit()
    session.refresh(task)
    publish_task_event("task_finished", task)
    discord_notify.notify_task("finished", task, payload.summary)
    return task


def fail_task(session: Session, task: Task, payload: TaskFailPayload) -> Task:
    ensure_not_terminal(task, "fail")
    task.status = TaskStatus.failed
    task.error_message = payload.error
    if payload.tests is not None:
        task.tests_status = payload.tests
    if payload.build is not None:
        task.build_status = payload.build
    if payload.exit_code is not None:
        task.exit_code = payload.exit_code
    task.finished_at = utcnow()
    session.add(task)
    add_event(session, task, "agent_failed", payload.error)
    session.commit()
    session.refresh(task)
    publish_task_event("task_failed", task)
    discord_notify.notify_task("failed", task, payload.error)
    return task


def block_task(session: Session, task: Task, reason: str) -> Task:
    ensure_not_terminal(task, "block")
    task.status = TaskStatus.blocked
    session.add(task)
    add_event(session, task, "waiting_for_user", f"Blocked: {reason}", metadata={"reason": reason})
    session.commit()
    session.refresh(task)
    publish_task_event("task_status_changed", task)
    discord_notify.notify_task("blocked", task, reason)
    return task


def cancel_task(session: Session, task: Task, reason: str | None) -> Task:
    ensure_not_terminal(task, "cancel")
    task.status = TaskStatus.cancelled
    task.finished_at = task.finished_at or utcnow()
    session.add(task)
    add_event(session, task, "task_cancelled", reason or "Task cancelled")
    session.commit()
    session.refresh(task)
    publish_task_event("task_status_changed", task)
    return task


def approve_task(session: Session, task: Task, review_note: str | None) -> Task:
    if task.status not in {TaskStatus.needs_review, TaskStatus.waiting_for_approval}:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task.public_id} is '{task.status.value}', only tasks in "
                   "needs_review/waiting_for_approval can be approved",
        )
    task.status = TaskStatus.completed
    task.approved_at = utcnow()
    if review_note:
        task.review_note = review_note
    session.add(task)
    add_event(session, task, "task_approved", review_note or "Task approved")
    session.commit()
    session.refresh(task)
    publish_task_event("task_approved", task)
    return task


def reject_task(session: Session, task: Task, review_note: str) -> Task:
    if task.status not in {TaskStatus.needs_review, TaskStatus.waiting_for_approval}:
        raise HTTPException(
            status_code=409,
            detail=f"Task {task.public_id} is '{task.status.value}', only tasks in "
                   "needs_review/waiting_for_approval can be rejected",
        )
    task.status = TaskStatus.rejected
    task.rejected_at = utcnow()
    task.review_note = review_note
    session.add(task)
    add_event(session, task, "task_rejected", review_note)
    session.commit()
    session.refresh(task)
    publish_task_event("task_rejected", task)
    return task


def archive_task(session: Session, task: Task) -> Task:
    task.is_archived = True
    session.add(task)
    add_event(session, task, "task_archived", f"{task.public_id} archived", touch_activity=False)
    session.commit()
    session.refresh(task)
    publish_task_event("task_status_changed", task, {"is_archived": True})
    return task
