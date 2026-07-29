from anyio import to_thread
from fastapi import APIRouter
from fastapi.responses import FileResponse

from ..config import get_settings
from ..dependencies import WriteAuth
from ..schemas.system import (
    ScreenshotCaptureResult,
    ScreenshotInstallResult,
    ScreenshotStatus,
)
from ..services import screenshot

router = APIRouter(prefix="/system", tags=["system"])


# --- Screenshots -----------------------------------------------------------


@router.get("/screenshot/status", response_model=ScreenshotStatus)
async def screenshot_status() -> ScreenshotStatus:
    """Whether the mss screenshot library is installed in the backend venv."""
    return await to_thread.run_sync(screenshot.read_status)


@router.post("/screenshot/install", response_model=ScreenshotInstallResult, dependencies=[WriteAuth])
async def screenshot_install() -> ScreenshotInstallResult:
    """Installs mss into the backend venv via pip."""
    settings = get_settings()
    return await to_thread.run_sync(
        screenshot.run_install,
        settings.screenshot_install_timeout_seconds,
    )


@router.post("/screenshot/capture", response_model=ScreenshotCaptureResult, dependencies=[WriteAuth])
async def screenshot_capture() -> ScreenshotCaptureResult:
    """Captures the server's primary monitor to a PNG and returns its URL."""
    settings = get_settings()
    return await to_thread.run_sync(screenshot.capture, settings.screenshot_dir)


@router.get("/screenshot/file/{filename}")
async def screenshot_file(filename: str) -> FileResponse:
    """Serves a previously captured PNG. Read-only, so no auth in V1."""
    settings = get_settings()
    path = screenshot.resolve_file(settings.screenshot_dir, filename)
    return FileResponse(path, media_type="image/png")
