from pydantic import BaseModel

__all__ = [
    "ScreenshotCaptureResult",
    "ScreenshotInstallResult",
    "ScreenshotStatus",
]


class ScreenshotStatus(BaseModel):
    # Whether the "mss" screenshot library is importable in the backend venv.
    installed: bool
    # mss.__version__, None when it is not installed.
    version: str | None = None
    # The Python interpreter mss would be installed into (the backend venv).
    python_path: str = ""
    detail: str = ""


class ScreenshotInstallResult(BaseModel):
    ok: bool
    exit_code: int
    output: str
    status: ScreenshotStatus


class ScreenshotCaptureResult(BaseModel):
    ok: bool
    # Basename of the saved PNG; combine with the file endpoint to view it.
    filename: str | None = None
    # Ready-to-use URL path the dashboard can render directly.
    url: str | None = None
    # ISO-8601 UTC timestamp of the capture.
    taken_at: str | None = None
    width: int = 0
    height: int = 0
    detail: str = ""
