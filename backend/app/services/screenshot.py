"""Capture screenshots of the server's screen with the "mss" library.

Two responsibilities, mirroring the OpenACP install feature:
  * install mss into the backend venv from the dashboard, and report whether it
    is present;
  * capture the primary monitor to a PNG the dashboard can then display.

SECURITY: the only subprocess is a fixed "pip install mss" into this very
interpreter — shell=False, no user input. Capture happens in-process.

Note: mss grabs whatever desktop the backend process is attached to. This only
does something useful when Agent Deck runs as a normal desktop app on the main
PC, which is exactly how it is deployed.
"""

import importlib
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from ..schemas.system import ScreenshotCaptureResult, ScreenshotInstallResult, ScreenshotStatus

PACKAGE = "mss"
MAX_OUTPUT_CHARS = 8192

# Only a timestamp varies in the filename; keep it filesystem-safe.
_FILENAME_RE = re.compile(r"^screenshot-[0-9T\-]+\.png$")

# One pip install at a time — two would fight over the same site-packages.
_install_lock = threading.Lock()


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated"


def _load_mss():
    """Imports mss fresh so a just-installed package is picked up without a
    backend restart. Returns the module, or None when it is not installed."""
    try:
        # invalidate_caches lets the import system see files pip wrote after
        # this long-running process started.
        importlib.invalidate_caches()
        module = importlib.import_module(PACKAGE)
        return importlib.reload(module) if PACKAGE in sys.modules else module
    except ImportError:
        return None


def read_status() -> ScreenshotStatus:
    """Never raises."""
    module = _load_mss()
    if module is None:
        return ScreenshotStatus(
            installed=False,
            version=None,
            python_path=sys.executable,
            detail="mss is not installed. Click Install to add it to the backend venv.",
        )
    return ScreenshotStatus(
        installed=True,
        version=getattr(module, "__version__", None),
        python_path=sys.executable,
        detail="mss is installed.",
    )


def run_install(timeout: int) -> ScreenshotInstallResult:
    """pip install mss into the backend interpreter."""
    if not _install_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A screenshot-library install is already running")

    try:
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
                [sys.executable, "-m", "pip", "install", PACKAGE],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"pip install timed out after {timeout}s")

        output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))
        ok = result.returncode == 0

        return ScreenshotInstallResult(
            ok=ok,
            exit_code=result.returncode,
            output=output or ("mss installed" if ok else "pip install failed"),
            status=read_status(),
        )
    finally:
        _install_lock.release()


def capture(output_dir: str) -> ScreenshotCaptureResult:
    """Grabs the primary monitor to a timestamped PNG under output_dir."""
    module = _load_mss()
    if module is None:
        raise HTTPException(
            status_code=422,
            detail="mss is not installed — install it first.",
        )

    now = datetime.now(timezone.utc)
    # Colons are illegal in Windows filenames, so the timestamp uses dashes.
    stamp = now.strftime("%Y-%m-%dT%H-%M-%S")
    filename = f"screenshot-{stamp}.png"

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / filename

    try:
        with module.mss() as sct:
            # monitors[0] is the full virtual desktop; [1] is the primary
            # display. Prefer the primary, fall back to the whole desktop.
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            shot = sct.grab(monitor)
            module.tools.to_png(shot.rgb, shot.size, output=str(target))
    except Exception as exc:  # noqa: BLE001 - surface any capture failure to the UI
        raise HTTPException(status_code=500, detail=f"Screenshot capture failed: {exc}")

    return ScreenshotCaptureResult(
        ok=True,
        filename=filename,
        url=f"/api/system/screenshot/file/{filename}",
        taken_at=now.isoformat(),
        width=shot.size.width,
        height=shot.size.height,
        detail="Captured the primary monitor.",
    )


def resolve_file(output_dir: str, filename: str) -> Path:
    """Validates a requested filename and returns its path, or 404s.

    The regex keeps this endpoint from serving anything but its own captures —
    no traversal, no arbitrary reads.
    """
    if not _FILENAME_RE.match(filename):
        raise HTTPException(status_code=404, detail="Not found")
    path = Path(output_dir) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    return path
