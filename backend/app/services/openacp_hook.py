"""Runs the channel-bindings install-hook script.

SECURITY: this is the only place in Agent Deck that executes a subprocess. It
runs one fixed script with a fixed argument list — no shell, no user-supplied
input reaches the command line, and a timeout bounds it.
"""

import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from ..schemas.openacp import HookStatusRead, RedeployResult

SCRIPT_RELATIVE = Path("scripts") / "install-hook.mjs"
BUILD_MARKER = Path("dist") / "index.js"
MAX_OUTPUT_CHARS = 8192

# install-hook.mjs copies files into the adapter directory; two concurrent runs
# would interleave those copies.
_redeploy_lock = threading.Lock()


def _script_path(module_dir: str) -> Path:
    return Path(module_dir) / SCRIPT_RELATIVE


def _node_executable() -> str:
    return shutil.which("node") or "node"


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated"


def _run(module_dir: str, timeout: int, check_only: bool) -> subprocess.CompletedProcess[str]:
    argv = [_node_executable(), str(_script_path(module_dir))]
    if check_only:
        argv.append("--check")
    return subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
        argv,
        cwd=module_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


def check_hook(module_dir: str, timeout: int) -> HookStatusRead:
    """--check exits 0 when installed and 2 when not. Exit 2 is an answer, not a failure."""
    now = datetime.now(timezone.utc)

    if not _script_path(module_dir).is_file():
        return HookStatusRead(
            installed=None,
            detail=f"install-hook.mjs not found in {module_dir}",
            checked_at=now,
        )

    try:
        result = _run(module_dir, timeout, check_only=True)
    except FileNotFoundError:
        return HookStatusRead(
            installed=None,
            detail="node was not found on the backend's PATH",
            checked_at=now,
        )
    except subprocess.TimeoutExpired:
        return HookStatusRead(installed=None, detail="hook check timed out", checked_at=now)

    if result.returncode == 0:
        return HookStatusRead(installed=True, detail="Hook is installed in the adapter", checked_at=now)
    if result.returncode == 2:
        return HookStatusRead(
            installed=False,
            detail="Hook is not installed — run Redeploy",
            checked_at=now,
        )
    return HookStatusRead(
        installed=None,
        detail=_truncate(result.stderr or result.stdout) or "hook check failed",
        checked_at=now,
    )


def run_redeploy(module_dir: str, timeout: int) -> RedeployResult:
    script = _script_path(module_dir)
    if not script.is_file():
        raise HTTPException(status_code=422, detail=f"install-hook.mjs not found in {module_dir}")
    if not (Path(module_dir) / BUILD_MARKER).is_file():
        # The script would fail with a confusing message; be actionable instead.
        raise HTTPException(
            status_code=422,
            detail='The channel-bindings module is not built — run "npm run build" in '
            f"{module_dir} first.",
        )

    if not _redeploy_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A redeploy is already running")

    try:
        try:
            result = _run(module_dir, timeout, check_only=False)
        except FileNotFoundError:
            raise HTTPException(status_code=422, detail="node was not found on the backend's PATH")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail="Redeploy timed out")

        output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))
        ok = result.returncode == 0
        installed = True if ok else None

        return RedeployResult(
            ok=ok,
            installed=installed,
            exit_code=result.returncode,
            output=output or ("Redeploy finished" if ok else "Redeploy failed"),
        )
    finally:
        _redeploy_lock.release()
