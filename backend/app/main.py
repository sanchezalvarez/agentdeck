import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import get_settings
from .routers import dashboard, events, health, openacp, projects, system, tasks, workers

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

# Reject unreasonably large request bodies (protects the local SQLite store).
MAX_BODY_BYTES = 2 * 1024 * 1024


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Agent Deck",
        version=__version__,
        description="Local hub that records and displays work performed by Claude Code and Codex agents.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def limit_body_size(request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_BODY_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large"})
        return await call_next(request)

    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(projects.router, prefix=api_prefix)
    app.include_router(tasks.router, prefix=api_prefix)
    app.include_router(workers.router, prefix=api_prefix)
    app.include_router(dashboard.router, prefix=api_prefix)
    app.include_router(events.router, prefix=api_prefix)
    app.include_router(openacp.router, prefix=api_prefix)
    app.include_router(system.router, prefix=api_prefix)

    return app


app = create_app()
