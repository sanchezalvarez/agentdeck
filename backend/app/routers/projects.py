from fastapi import APIRouter, HTTPException
from sqlmodel import select

from ..dependencies import SessionDep, WriteAuth
from ..models import Project
from ..schemas.project import ProjectCreate, ProjectRead, ProjectUpdate, slugify
from ..utils.time import utcnow

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=201, dependencies=[WriteAuth])
async def create_project(payload: ProjectCreate, session: SessionDep) -> Project:
    slug = payload.slug or slugify(payload.name)
    if not slug:
        raise HTTPException(status_code=422, detail="Could not derive a slug from the project name")
    existing = session.exec(select(Project).where(Project.slug == slug)).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Project with slug '{slug}' already exists")
    project = Project(
        name=payload.name,
        slug=slug,
        repository_path=payload.repository_path,
        default_branch=payload.default_branch,
        project_type=payload.project_type,
        is_active=payload.is_active,
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.get("", response_model=list[ProjectRead])
async def list_projects(session: SessionDep, active: bool | None = None) -> list[Project]:
    query = select(Project).order_by(Project.name)
    if active is not None:
        query = query.where(Project.is_active == active)
    return list(session.exec(query).all())


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: int, session: SessionDep) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead, dependencies=[WriteAuth])
async def update_project(project_id: int, payload: ProjectUpdate, session: SessionDep) -> Project:
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    data = payload.model_dump(exclude_unset=True)
    if "slug" in data and data["slug"] != project.slug:
        existing = session.exec(select(Project).where(Project.slug == data["slug"])).first()
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"Project with slug '{data['slug']}' already exists")
    for key, value in data.items():
        setattr(project, key, value)
    project.updated_at = utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)
    return project
