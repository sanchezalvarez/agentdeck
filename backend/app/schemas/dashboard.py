from pydantic import BaseModel

from .project import ProjectSummary
from .task import TaskRead
from .worker import WorkerRead


class DashboardSummary(BaseModel):
    running_count: int
    waiting_for_user_count: int
    waiting_for_approval_count: int
    needs_review_count: int
    failed_today_count: int
    completed_today_count: int
    active_tasks: list[TaskRead]
    recent_failed_tasks: list[TaskRead]
    workers: list[WorkerRead]
    projects: list[ProjectSummary]
