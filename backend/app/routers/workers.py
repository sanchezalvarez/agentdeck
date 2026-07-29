from fastapi import APIRouter, HTTPException
from sqlmodel import select

from ..dependencies import SessionDep, WriteAuth
from ..models import Worker
from ..schemas.worker import WorkerHeartbeat, WorkerRead
from ..services.broadcaster import broadcaster
from ..services.serializers import worker_to_read
from ..utils.time import utcnow

router = APIRouter(prefix="/workers", tags=["workers"])


@router.get("", response_model=list[WorkerRead])
async def list_workers(session: SessionDep) -> list[WorkerRead]:
    workers = session.exec(select(Worker).order_by(Worker.name)).all()
    return [worker_to_read(w) for w in workers]


@router.get("/{worker_id}", response_model=WorkerRead)
async def get_worker(worker_id: int, session: SessionDep) -> WorkerRead:
    worker = session.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker_to_read(worker)


@router.post("/heartbeat", response_model=WorkerRead, dependencies=[WriteAuth])
async def heartbeat(payload: WorkerHeartbeat, session: SessionDep) -> WorkerRead:
    worker = session.exec(select(Worker).where(Worker.name == payload.worker)).first()
    if worker is None:
        worker = Worker(name=payload.worker)
        session.add(worker)
    now = utcnow()
    worker.last_seen_at = now
    worker.updated_at = now
    worker.status = payload.status
    if payload.hostname is not None:
        worker.hostname = payload.hostname
    if payload.operating_system is not None:
        worker.operating_system = payload.operating_system
    for field in ("claude_available", "codex_available", "unity_available", "unity_mcp_available"):
        value = getattr(payload, field)
        if value is not None:
            setattr(worker, field, value)
    session.add(worker)
    session.commit()
    session.refresh(worker)
    result = worker_to_read(worker)
    broadcaster.publish(
        "worker_heartbeat",
        {"id": worker.id, "name": worker.name, "status": worker.status.value,
         "last_seen_at": worker.last_seen_at.isoformat() if worker.last_seen_at else None},
    )
    return result
