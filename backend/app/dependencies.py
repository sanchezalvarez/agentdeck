import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlmodel import Session

from .config import get_settings
from .database import get_session

SessionDep = Annotated[Session, Depends(get_session)]


def require_write_token(authorization: Annotated[str | None, Header()] = None) -> None:
    """Write endpoints require `Authorization: Bearer <AGENT_HUB_WRITE_TOKEN>`.

    When AGENT_HUB_WRITE_TOKEN is empty, writes are allowed without a token
    (local development mode). The token value is never logged.
    """
    token = get_settings().write_token
    if not token:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    provided = authorization[len("Bearer "):].strip()
    if not secrets.compare_digest(provided, token):
        raise HTTPException(status_code=401, detail="Invalid write token")


WriteAuth = Depends(require_write_token)
