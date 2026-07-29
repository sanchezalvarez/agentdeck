from enum import Enum


class ProjectType(str, Enum):
    web = "web"
    unity = "unity"
    desktop = "desktop"
    backend = "backend"
    other = "other"


class WorkerStatus(str, Enum):
    online = "online"
    offline = "offline"
    degraded = "degraded"
    unknown = "unknown"


class AgentType(str, Enum):
    claude = "claude"
    codex = "codex"


class TaskStatus(str, Enum):
    queued = "queued"
    starting = "starting"
    running = "running"
    waiting_for_user = "waiting_for_user"
    waiting_for_approval = "waiting_for_approval"
    testing = "testing"
    needs_review = "needs_review"
    completed = "completed"
    blocked = "blocked"
    failed = "failed"
    cancelled = "cancelled"
    rejected = "rejected"


# Statuses in which an agent is still allowed to report activity.
ACTIVE_TASK_STATUSES = {
    TaskStatus.queued,
    TaskStatus.starting,
    TaskStatus.running,
    TaskStatus.waiting_for_user,
    TaskStatus.waiting_for_approval,
    TaskStatus.testing,
    TaskStatus.blocked,
}

TERMINAL_TASK_STATUSES = {
    TaskStatus.completed,
    TaskStatus.cancelled,
    TaskStatus.rejected,
}


class TaskPriority(str, Enum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class CheckStatus(str, Enum):
    """Status of tests or builds."""

    pending = "pending"
    running = "running"
    passed = "passed"
    failed = "failed"
    not_run = "not_run"


class ArtifactType(str, Enum):
    log = "log"
    screenshot = "screenshot"
    test_report = "test_report"
    build = "build"
    diff = "diff"
    patch = "patch"
    document = "document"
    other = "other"


# Well-known event types. The event_type column intentionally stays an open
# string so future event types are not blocked; these are the documented ones.
KNOWN_EVENT_TYPES = [
    "task_created",
    "task_started",
    "agent_started",
    "progress",
    "command_started",
    "command_finished",
    "tests_started",
    "tests_finished",
    "build_started",
    "build_finished",
    "waiting_for_user",
    "waiting_for_approval",
    "artifact_added",
    "agent_finished",
    "agent_failed",
    "task_cancelled",
    "review_requested",
    "task_approved",
    "task_rejected",
    "task_archived",
    "worker_heartbeat",
]
