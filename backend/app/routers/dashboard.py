from datetime import datetime, time, timedelta

from fastapi import APIRouter
from sqlmodel import col, func, select

from ..dependencies import SessionDep
from ..models import Project, Task, TaskStatus, Worker
from ..schemas.dashboard import DashboardSummary
from ..schemas.project import ProjectRead, ProjectSummary
from ..services.serializers import task_to_read, worker_to_read
from ..utils.time import utcnow

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

ACTIVE_STATUSES = [
    TaskStatus.queued,
    TaskStatus.starting,
    TaskStatus.running,
    TaskStatus.waiting_for_user,
    TaskStatus.waiting_for_approval,
    TaskStatus.testing,
    TaskStatus.blocked,
]


def _count(session, *conditions) -> int:
    value = session.exec(select(func.count()).select_from(Task).where(*conditions)).one()
    if isinstance(value, tuple):
        value = value[0]
    return int(value)


@router.get("/summary", response_model=DashboardSummary)
async def dashboard_summary(session: SessionDep) -> DashboardSummary:
    today_start = datetime.combine(utcnow().date(), time.min)
    not_archived = Task.is_archived == False  # noqa: E712

    running_count = _count(session, Task.status == TaskStatus.running, not_archived)
    waiting_user = _count(session, Task.status == TaskStatus.waiting_for_user, not_archived)
    waiting_approval = _count(session, Task.status == TaskStatus.waiting_for_approval, not_archived)
    needs_review = _count(session, Task.status == TaskStatus.needs_review, not_archived)
    failed_today = _count(
        session, Task.status == TaskStatus.failed, Task.finished_at >= today_start, not_archived
    )
    completed_today = _count(
        session, Task.status == TaskStatus.completed, Task.approved_at >= today_start, not_archived
    )

    active_tasks = session.exec(
        select(Task)
        .where(col(Task.status).in_(ACTIVE_STATUSES), not_archived)
        .order_by(col(Task.last_activity_at).desc())
        .limit(50)
    ).all()

    recent_failed = session.exec(
        select(Task)
        .where(Task.status == TaskStatus.failed, not_archived)
        .order_by(col(Task.finished_at).desc())
        .limit(10)
    ).all()

    workers = session.exec(select(Worker).order_by(Worker.name)).all()

    projects = session.exec(select(Project).order_by(Project.name)).all()
    project_summaries: list[ProjectSummary] = []
    for project in projects:
        last_completed = session.exec(
            select(Task)
            .where(Task.project_id == project.id, Task.status == TaskStatus.completed)
            .order_by(col(Task.approved_at).desc())
            .limit(1)
        ).first()
        project_summaries.append(
            ProjectSummary(
                project=ProjectRead.model_validate(project),
                running_tasks=_count(
                    session, Task.project_id == project.id,
                    col(Task.status).in_([TaskStatus.running, TaskStatus.testing, TaskStatus.starting]),
                    not_archived,
                ),
                needs_review_tasks=_count(
                    session, Task.project_id == project.id,
                    Task.status == TaskStatus.needs_review, not_archived,
                ),
                failed_tasks=_count(
                    session, Task.project_id == project.id,
                    Task.status == TaskStatus.failed, not_archived,
                ),
                last_completed_task_id=last_completed.public_id if last_completed else None,
                last_completed_at=last_completed.approved_at if last_completed else None,
            )
        )

    return DashboardSummary(
        running_count=running_count,
        waiting_for_user_count=waiting_user,
        waiting_for_approval_count=waiting_approval,
        needs_review_count=needs_review,
        failed_today_count=failed_today,
        completed_today_count=completed_today,
        active_tasks=[task_to_read(t) for t in active_tasks],
        recent_failed_tasks=[task_to_read(t) for t in recent_failed],
        workers=[worker_to_read(w) for w in workers],
        projects=project_summaries,
    )
