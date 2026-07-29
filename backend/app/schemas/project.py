import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from ..models.enums import ProjectType

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,98}[a-z0-9]$|^[a-z0-9]$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return slug[:100]


class ProjectCreate(BaseModel):
    name: str
    slug: str | None = None
    repository_path: str | None = None
    default_branch: str = "main"
    project_type: ProjectType = ProjectType.other
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be empty")
        return v

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must contain only lowercase letters, digits and dashes")
        return v


class ProjectUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    repository_path: str | None = None
    default_branch: str | None = None
    project_type: ProjectType | None = None
    is_active: bool | None = None

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().lower()
        if not SLUG_RE.match(v):
            raise ValueError("slug must contain only lowercase letters, digits and dashes")
        return v


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    repository_path: str | None
    default_branch: str
    project_type: ProjectType
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    """Project row enriched with task statistics for the dashboard."""

    project: ProjectRead
    running_tasks: int
    needs_review_tasks: int
    failed_tasks: int
    last_completed_task_id: str | None = None
    last_completed_at: datetime | None = None
