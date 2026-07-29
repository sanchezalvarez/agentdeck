"""Seed the local database with sample data for dashboard development.

Run manually (never automatically in production):

    cd backend
    .\\.venv\\Scripts\\Activate.ps1
    alembic upgrade head
    python -m app.seed
"""

import sys
from datetime import timedelta

from sqlalchemy import inspect
from sqlmodel import Session, select

from .database import get_engine
from .models import (
    AgentType,
    Artifact,
    ArtifactType,
    CheckStatus,
    Project,
    ProjectType,
    Task,
    TaskEvent,
    TaskPriority,
    TaskStatus,
    Worker,
    WorkerStatus,
)
from .utils.time import utcnow


def seed() -> None:
    engine = get_engine()
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        print("ERROR: database tables are missing. Run migrations first:")
        print("  alembic upgrade head")
        sys.exit(1)

    with Session(engine) as session:
        if session.exec(select(Task)).first() is not None:
            print("Database already contains tasks — seed skipped (no data was changed).")
            return

        now = utcnow()

        crowforge = Project(name="CrowForge", slug="crowforge", project_type=ProjectType.desktop,
                            repository_path=r"D:\Projects\CrowForge", default_branch="main")
        unity_game = Project(name="Unity Game", slug="unity-game", project_type=ProjectType.unity,
                             repository_path=r"D:\Projects\UnityGame", default_branch="main")
        web = Project(name="Rembrosoft Web", slug="rembrosoft-web", project_type=ProjectType.web,
                      repository_path=r"D:\Projects\RembrosoftWeb", default_branch="main")
        session.add(crowforge)
        session.add(unity_game)
        session.add(web)

        worker = Worker(
            name="Rembrosoft-Main-PC", hostname="REMBRO-MAIN", operating_system="Windows 11",
            status=WorkerStatus.online, last_seen_at=now,
            claude_available=True, codex_available=True, unity_available=True, unity_mcp_available=False,
        )
        session.add(worker)
        session.flush()

        def make_task(num: int, **kwargs) -> Task:
            task = Task(public_id=f"REM-{num:03d}", **kwargs)
            session.add(task)
            session.flush()
            session.add(TaskEvent(task_id=task.id, event_type="task_created",
                                  message=f"Task created: {task.title}", created_at=task.created_at))
            return task

        t1 = make_task(
            1, title="Fix DOCX table import", project_id=crowforge.id,
            description="Table borders and alignment are lost when importing DOCX files.",
            agent_type=AgentType.claude, status=TaskStatus.running, priority=TaskPriority.high,
            requested_by="Lubomir", worker_id=worker.id,
            branch="agent/rem-001-docx", working_directory=r"D:\AgentWorkspaces\crowforge-claude",
            created_at=now - timedelta(hours=2), started_at=now - timedelta(hours=1),
            last_activity_at=now - timedelta(minutes=5),
        )
        session.add(TaskEvent(task_id=t1.id, event_type="task_started",
                              message="Agent started working", created_at=t1.started_at))
        session.add(TaskEvent(task_id=t1.id, event_type="progress",
                              message="Implemented table style parsing",
                              created_at=now - timedelta(minutes=5)))

        t2 = make_task(
            2, title="Add player inventory UI", project_id=unity_game.id,
            description="Grid-based inventory with drag & drop.",
            agent_type=AgentType.codex, status=TaskStatus.needs_review, priority=TaskPriority.normal,
            requested_by="Lubomir", worker_id=worker.id, branch="agent/rem-002-inventory",
            tests_status=CheckStatus.passed, build_status=CheckStatus.passed, exit_code=0,
            result_summary="Implemented inventory UI with drag & drop and 14 new play-mode tests.",
            created_at=now - timedelta(days=1), started_at=now - timedelta(days=1),
            finished_at=now - timedelta(hours=3), last_activity_at=now - timedelta(hours=3),
        )
        session.add(TaskEvent(task_id=t2.id, event_type="agent_finished",
                              message=t2.result_summary, created_at=t2.finished_at))
        session.add(TaskEvent(task_id=t2.id, event_type="review_requested",
                              message="REM-002 is ready for review", created_at=t2.finished_at))
        session.add(Artifact(task_id=t2.id, artifact_type=ArtifactType.screenshot,
                             name="Inventory preview",
                             local_path=r"D:\AgentWorkspaces\artifacts\inventory.png"))

        t3 = make_task(
            3, title="Update landing page hero section", project_id=web.id,
            description="New copy and CTA button.",
            agent_type=AgentType.claude, status=TaskStatus.completed, priority=TaskPriority.low,
            requested_by="Lubomir", worker_id=worker.id, branch="agent/rem-003-hero",
            tests_status=CheckStatus.passed, build_status=CheckStatus.passed, exit_code=0,
            result_summary="Hero section updated, lint/typecheck/build pass.",
            created_at=now - timedelta(days=2), started_at=now - timedelta(days=2),
            finished_at=now - timedelta(days=2, hours=-1),
            approved_at=now - timedelta(hours=1), review_note="Looks good.",
            last_activity_at=now - timedelta(hours=1),
        )
        session.add(TaskEvent(task_id=t3.id, event_type="task_approved",
                              message="Looks good.", created_at=t3.approved_at))

        t4 = make_task(
            4, title="Migrate build pipeline to .NET 9", project_id=crowforge.id,
            description="Upgrade SDK and fix breaking changes.",
            agent_type=AgentType.codex, status=TaskStatus.failed, priority=TaskPriority.normal,
            requested_by="Lubomir", worker_id=worker.id,
            tests_status=CheckStatus.failed, build_status=CheckStatus.failed, exit_code=1,
            error_message="Build failed: incompatible NuGet package 'LegacyDocx 2.1'.",
            created_at=now - timedelta(hours=8), started_at=now - timedelta(hours=8),
            finished_at=now - timedelta(hours=6), last_activity_at=now - timedelta(hours=6),
        )
        session.add(TaskEvent(task_id=t4.id, event_type="agent_failed",
                              message=t4.error_message, created_at=t4.finished_at))

        t5 = make_task(
            5, title="Refactor save-game serialization", project_id=unity_game.id,
            description="Move to versioned JSON save format.",
            agent_type=AgentType.claude, status=TaskStatus.blocked, priority=TaskPriority.normal,
            requested_by="Lubomir", worker_id=worker.id,
            created_at=now - timedelta(hours=5), started_at=now - timedelta(hours=5),
            last_activity_at=now - timedelta(hours=4),
        )
        session.add(TaskEvent(task_id=t5.id, event_type="waiting_for_user",
                              message="Blocked: need decision on backwards compatibility with v0 saves.",
                              created_at=now - timedelta(hours=4)))

        make_task(
            6, title="Add sitemap.xml generation", project_id=web.id,
            description="Generate sitemap during the production build.",
            status=TaskStatus.queued, priority=TaskPriority.low, requested_by="Lubomir",
            created_at=now - timedelta(minutes=30), last_activity_at=now - timedelta(minutes=30),
        )

        session.commit()
        print("Seed complete: 3 projects, 1 worker, 6 sample tasks (REM-001 … REM-006).")


if __name__ == "__main__":
    seed()
