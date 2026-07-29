from fastapi import APIRouter
from sqlmodel import text

from .. import __version__
from ..dependencies import SessionDep
from ..utils.time import utcnow

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(session: SessionDep) -> dict:
    database = "ok"
    try:
        session.exec(text("SELECT 1"))
    except Exception:
        database = "error"
    return {
        "status": "ok" if database == "ok" else "degraded",
        "database": database,
        "time_utc": utcnow().isoformat() + "Z",
        "version": __version__,
    }
