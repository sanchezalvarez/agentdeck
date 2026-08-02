"""Control the OpenACP daemon through its CLI.

SECURITY: like openacp_hook, every call here is a fixed argument list with
shell=False and no user-supplied input. The only variability is which of the
known subcommands runs ("status", "stop", "start").

OpenACP runs in foreground mode, so a restart is stop + a fresh process in its
own console window (see _spawn_foreground) rather than "openacp restart".

Restarting or stopping the daemon terminates running agent sessions, so the
callers are expected to confirm with the user first — the count of sessions at
risk is exposed in DaemonStatusRead.active_sessions.
"""

import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from fastapi import HTTPException

from ..schemas.openacp import (
    AgentInstallResult,
    DaemonActionResult,
    DaemonStatusRead,
    DoctorCategory,
    DoctorCheck,
    DoctorResult,
    OpenAcpSessionRead,
    SessionActionResult,
)

MAX_OUTPUT_CHARS = 4096

# Curated subset of the ACP registry (28+ entries — "openacp agents") that the
# dashboard offers a one-click install for. Anything else can still be
# installed by hand with "openacp agents install <name>"; this list exists so
# the button only ever sends a known-good id, never an arbitrary string typed
# into a request. Keep in sync with AGENT_CATALOG in
# frontend/app/openacp/page.tsx.
AGENT_CATALOG = {
    "claude": "Claude Agent",
    "codex": "Codex",
    "gemini": "Gemini CLI",
    "opencode": "OpenCode",
    "kimi": "Kimi CLI",
    "grok-build": "Grok Build",
}
# Sessions in these states hold resources and would be lost on restart.
ACTIVE_SESSION_STATES = {"active", "initializing"}

# A foreground instance owns a console window and writes no pid file, so the
# OpenACP CLI cannot touch it. These scripts kill its node process directly and,
# for a restart, spawn a fresh window. Fixed names — never built from input.
FOREGROUND_SCRIPTS = {"restart": "restart-openacp.ps1", "stop": "stop-openacp.ps1"}

CREATE_NEW_CONSOLE = 0x00000010
# How long to wait for a restarted OpenACP to report itself online.
STARTUP_TIMEOUT_SECONDS = 20
STARTUP_POLL_SECONDS = 1.0
# Give the old process time to release its lock before starting a new one.
STOP_SETTLE_SECONDS = 2.0

# Serialises restart/stop so two clicks cannot overlap.
_action_lock = threading.Lock()

# Session ids as issued by OpenACP (short base64url-like strings). Anything else
# is rejected before it can reach the CLI argument list.
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _cli_path() -> str | None:
    # On Windows this resolves to openacp.CMD, which subprocess runs directly.
    return shutil.which("openacp")


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated"


def _run(args: list[str], timeout: int, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    cli = _cli_path()
    if not cli:
        raise FileNotFoundError("openacp not found on PATH")
    return subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
        [cli, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
        cwd=cwd,
    )


def _spawn_foreground(args: list[str], cwd: str | None) -> None:
    """Starts OpenACP in a console window of its own and returns immediately.

    OpenACP runs with runMode=foreground, so it cannot be started with
    subprocess.run: the call would block until OpenACP exits, and the process
    would be a child of this request, dying with it. CREATE_NEW_CONSOLE gives it
    its own visible window, which is also where its log ends up.
    """
    cli = _cli_path()
    if not cli:
        raise FileNotFoundError("openacp not found on PATH")

    kwargs: dict = {}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NEW_CONSOLE

    subprocess.Popen(  # noqa: S603 - fixed argv, shell=False, no user input
        [cli, *args],
        cwd=cwd,
        shell=False,
        close_fds=True,
        **kwargs,
    )


def _powershell() -> str | None:
    """pwsh when installed, Windows PowerShell otherwise — the rule agent-deck.bat uses."""
    return shutil.which("pwsh") or shutil.which("powershell")


def _run_foreground_script(
    action: str, scripts_dir: str, timeout: int, sessions_path: str
) -> DaemonActionResult:
    """Drives a foreground instance through the repository's own scripts.

    SECURITY: the script name comes from FOREGROUND_SCRIPTS, never from input,
    and the argument list is fixed — the same shape as openacp_hook.
    """
    shell = _powershell()
    if not shell:
        raise HTTPException(
            status_code=503, detail="PowerShell was not found on the backend's PATH"
        )

    script = Path(scripts_dir) / FOREGROUND_SCRIPTS[action]
    if not script.is_file():
        raise HTTPException(status_code=503, detail=f"{script.name} not found in {scripts_dir}")

    argv = [shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)]
    if action == "restart":
        # The dashboard already confirmed; the script must not wait on a prompt
        # nobody can answer.
        argv.append("-Force")

    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="PowerShell was not found on the backend's PATH")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail=f"openacp {action} timed out")

    output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))

    if action == "stop":
        status = read_status(timeout, sessions_path)
        # The script exits non-zero when the port is still answering.
        ok = result.returncode == 0 and not status.running
        return DaemonActionResult(
            ok=ok,
            action=action,
            output=output or ("OpenACP stopped" if ok else "OpenACP stop failed"),
            status=status,
        )

    status = _wait_until_running(timeout, sessions_path)
    message = (
        "OpenACP was restarted in its own console window."
        if status.running
        else f"OpenACP did not come back within {STARTUP_TIMEOUT_SECONDS}s — check its window."
    )
    return DaemonActionResult(
        ok=status.running,
        action=action,
        output=_truncate("\n".join(part for part in (output, message) if part)),
        status=status,
    )


def _wait_until_running(timeout: int, sessions_path: str) -> DaemonStatusRead:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    status = read_status(timeout, sessions_path)
    while not status.running and time.monotonic() < deadline:
        time.sleep(STARTUP_POLL_SECONDS)
        status = read_status(timeout, sessions_path)
    return status


def count_active_sessions(sessions_path: str) -> int:
    """Counts sessions a restart would kill. Best effort — never raises."""
    try:
        raw = Path(sessions_path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return 0

    sessions = data.get("sessions") if isinstance(data, dict) else None
    if not isinstance(sessions, list):
        return 0

    return sum(
        1
        for session in sessions
        if isinstance(session, dict) and session.get("status") in ACTIVE_SESSION_STATES
    )


def _probe_api(timeout: int) -> list | None:
    """Asks the running server directly, over its API port.

    This is the only way to see a foreground instance: it writes no PID file, so
    "openacp status" reports it as offline. Returns the live session list, or
    None when nothing answers.
    """
    try:
        result = _run(["api", "status", "--json"], timeout)
        payload = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None

    if not payload.get("success"):
        return None

    sessions = (payload.get("data") or {}).get("sessions")
    return sessions if isinstance(sessions, list) else None


def read_sessions(timeout: int) -> list[OpenAcpSessionRead]:
    """Live sessions from the running server, newest activity first.

    Returns an empty list when OpenACP is down — there is no stored copy of this
    data, so "nothing running" and "cannot ask" look the same to the caller. The
    daemon status endpoint is what tells the two apart.
    """
    raw = _probe_api(timeout)
    if not raw:
        return []

    sessions = [
        OpenAcpSessionRead(
            id=str(item.get("id") or ""),
            agent=str(item.get("agent") or ""),
            name=str(item.get("name") or ""),
            status=str(item.get("status") or "unknown"),
            active=item.get("status") in ACTIVE_SESSION_STATES,
            workspace=str(item.get("workspace") or ""),
            created_at=str(item.get("createdAt") or ""),
            last_active_at=str(item.get("lastActiveAt") or ""),
            prompt_running=bool(item.get("promptRunning")),
            queue_depth=int(item.get("queueDepth") or 0),
            dangerous_mode=bool(item.get("dangerousMode")),
        )
        for item in raw
        if isinstance(item, dict) and item.get("id")
    ]
    sessions.sort(key=lambda s: s.last_active_at, reverse=True)
    return sessions


def run_doctor(timeout: int) -> DoctorResult:
    """Runs "openacp doctor --json" — the CLI's own health check across
    config, agents, storage, workspace, plugins, daemon and tunnel.

    Never raises: an unreachable CLI, a timeout or unreadable output all
    report ok=False with a detail message, the same way read_status() treats
    a missing CLI as "unknown" rather than an error. This is a read-only
    diagnostic — no lock, no write.
    """
    if not _cli_path():
        return DoctorResult(ok=False, detail="openacp was not found on the backend's PATH")

    cwd = _workspace_dir(timeout)

    try:
        result = _run(["doctor", "--json"], timeout, cwd=cwd)
    except FileNotFoundError:
        return DoctorResult(ok=False, detail="openacp was not found on the backend's PATH")
    except subprocess.TimeoutExpired:
        return DoctorResult(ok=False, detail="openacp doctor timed out")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return DoctorResult(
            ok=False, detail=_truncate(result.stderr) or "could not read openacp doctor output"
        )

    if not payload.get("success"):
        return DoctorResult(ok=False, detail="openacp reported a failure")

    data = payload.get("data") or {}
    categories = [
        DoctorCategory(
            name=str(category.get("name") or ""),
            results=[
                DoctorCheck(status=str(check.get("status") or "unknown"), message=str(check.get("message") or ""))
                for check in (category.get("results") or [])
                if isinstance(check, dict)
            ],
        )
        for category in (data.get("categories") or [])
        if isinstance(category, dict)
    ]
    summary = data.get("summary") or {}

    return DoctorResult(
        ok=True,
        categories=categories,
        passed=int(summary.get("passed") or 0),
        warnings=int(summary.get("warnings") or 0),
        failed=int(summary.get("failed") or 0),
    )


def read_status(timeout: int, sessions_path: str) -> DaemonStatusRead:
    """Never raises — an unreachable CLI is reported as status "unknown"."""
    unknown = DaemonStatusRead(running=False, status="unknown", detail="")

    if not _cli_path():
        return unknown.model_copy(update={"detail": "openacp was not found on the backend's PATH"})

    try:
        result = _run(["status", "--json"], timeout)
    except FileNotFoundError:
        return unknown.model_copy(update={"detail": "openacp was not found on the backend's PATH"})
    except subprocess.TimeoutExpired:
        return unknown.model_copy(update={"detail": "openacp status timed out"})

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return unknown.model_copy(update={"detail": _truncate(result.stderr) or "could not read openacp status"})

    if not payload.get("success"):
        return unknown.model_copy(update={"detail": "openacp reported a failure"})

    data = payload.get("data") or {}
    status = str(data.get("status") or "unknown")
    running = status != "offline"
    channels = list(data.get("channels") or [])

    if not running:
        # No daemon — but a foreground instance may still be serving Discord.
        sessions = _probe_api(timeout)
        if sessions is not None:
            return DaemonStatusRead(
                running=True,
                status="online",
                pid=None,
                mode="foreground",
                channels=channels,
                active_sessions=sum(
                    1
                    for session in sessions
                    if isinstance(session, dict) and session.get("status") in ACTIVE_SESSION_STATES
                ),
                foreground=True,
                detail="Running in its own console window — restart or stop it there.",
            )

    return DaemonStatusRead(
        running=running,
        status=status,
        pid=data.get("pid"),
        mode=data.get("mode"),
        channels=channels,
        active_sessions=count_active_sessions(sessions_path) if running else 0,
        detail="",
    )


def cancel_session(session_id: str, timeout: int) -> SessionActionResult:
    """Cancels one session through the daemon API.

    Needed when a Discord thread is deleted: OpenACP never learns about the
    deletion, so its session keeps running until cancelled here. Unlike
    restart/stop this works for foreground instances too — "api cancel" talks
    to the API port, not the PID file.
    """
    if not _SESSION_ID_RE.match(session_id):
        raise HTTPException(status_code=422, detail="Invalid session id")

    try:
        result = _run(["api", "cancel", session_id, "--json"], timeout)
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="openacp api cancel timed out")

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502,
            detail=_truncate(result.stderr) or "could not read openacp api cancel output",
        )

    if not payload.get("success"):
        message = (payload.get("error") or {}).get("message") or "openacp reported a failure"
        raise HTTPException(status_code=502, detail=_truncate(str(message)))

    data = payload.get("data") or {}
    # Some failures come back success:true with an "error" key in data.
    if data.get("error"):
        raise HTTPException(status_code=502, detail=_truncate(str(data["error"])))

    return SessionActionResult(ok=bool(data.get("cancelled")), session_id=session_id)


def _run_agent_install(
    agent_id: str, cwd: str | None, timeout: int, force: bool = False
) -> subprocess.CompletedProcess[str]:
    args = ["agents", "install", agent_id]
    if force:
        args.append("--force")
    args.append("--json")
    return _run(args, timeout, cwd=cwd)


def _install_outcome(result: subprocess.CompletedProcess[str]) -> tuple[bool, dict | None]:
    """Whether an "openacp agents install --json" call actually succeeded.

    A zero exit code is not the whole story: like "api cancel" (see
    cancel_session above), the CLI can report success:true with an "error"
    tucked into data, or plain success:false, without a matching non-zero
    exit code.
    """
    ok = result.returncode == 0
    try:
        payload = json.loads(result.stdout) if result.stdout else None
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        if payload.get("success") is False:
            ok = False
        data = payload.get("data")
        if isinstance(data, dict) and data.get("error"):
            ok = False
    return ok, payload if isinstance(payload, dict) else None


def install_agent(agent_id: str, timeout: int) -> AgentInstallResult:
    """Installs one ACP agent plugin via "openacp agents install <id>".

    Restricted to AGENT_CATALOG even though the id never reaches a shell — the
    dashboard button should only ever send a known-good name, not an arbitrary
    string. Runs from the workspace directory (creating it if this is the
    first OpenACP action on this PC) for the same reason every other command
    here does.

    Shares _action_lock with restart/stop: it writes into the same workspace
    (agents.json) that a concurrent restart reads from and a concurrent
    install would collide with.
    """
    if agent_id not in AGENT_CATALOG:
        raise HTTPException(status_code=422, detail=f"Unknown agent id: {agent_id}")

    if not _cli_path():
        raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")

    if not _action_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another OpenACP action is already running")

    try:
        cwd = _workspace_dir(timeout)

        try:
            result = _run_agent_install(agent_id, cwd, timeout)
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"openacp agents install {agent_id} timed out")

        ok, payload = _install_outcome(result)

        # openacp can consider an agent "already installed" from some
        # global/npm-level check while this workspace's own agents.json was
        # never written — e.g. a workspace whose settings were restored from
        # another PC's bundle but that never itself ran an install. Plain
        # "already installed" is not a real failure, so retry once with
        # --force, which makes the CLI (re)write the workspace record instead
        # of just no-op'ing.
        error = (payload or {}).get("error") if payload else None
        code = error.get("code") if isinstance(error, dict) else None
        message = str(error.get("message") or "") if isinstance(error, dict) else ""
        if not ok and code == "INSTALL_FAILED" and "already installed" in message.lower():
            try:
                result = _run_agent_install(agent_id, cwd, timeout, force=True)
            except FileNotFoundError:
                raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")
            except subprocess.TimeoutExpired:
                raise HTTPException(
                    status_code=504, detail=f"openacp agents install {agent_id} --force timed out"
                )
            ok, payload = _install_outcome(result)

        output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))

        return AgentInstallResult(
            ok=ok,
            agent_id=agent_id,
            output=output or (f"{agent_id} installed" if ok else f"{agent_id} install failed"),
        )
    finally:
        _action_lock.release()


def _default_workspace_dir() -> str:
    """Falls back to the conventional workspace location, creating it if needed.

    "openacp status" has nothing to report on a genuinely fresh PC — there is no
    .openacp/ yet — so without this, restart/start would run with an
    unspecified cwd instead of the workspace OpenACP is supposed to initialize
    itself into. Mirrors the same default and creation scripts/start-openacp.ps1
    uses.
    """
    default = Path.home() / "openacp-workspace"
    default.mkdir(parents=True, exist_ok=True)
    return str(default)


def _workspace_dir(timeout: int) -> str:
    """The daemon must be driven from its workspace so it resolves the existing
    .openacp folder instead of creating a new one."""
    try:
        result = _run(["status", "--json"], timeout)
        payload = json.loads(result.stdout)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return _default_workspace_dir()

    directory = (payload.get("data") or {}).get("dir")
    if not directory:
        return _default_workspace_dir()
    return str(Path(directory).parent)


def run_action(
    action: str, timeout: int, sessions_path: str, scripts_dir: str, script_timeout: int
) -> DaemonActionResult:
    if action not in {"restart", "stop"}:
        raise HTTPException(status_code=422, detail="Unsupported daemon action")

    if not _cli_path():
        raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")

    if not _action_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Another OpenACP action is already running")

    try:
        # A foreground instance writes no PID file, so "openacp stop" cannot see
        # it and a plain restart would spawn a second instance fighting the first
        # one for the API port. The scripts kill its node process instead.
        current = read_status(timeout, sessions_path)
        if current.foreground:
            return _run_foreground_script(action, scripts_dir, script_timeout, sessions_path)

        cwd = _workspace_dir(timeout)

        # Both actions stop first; "openacp restart" is deliberately unused,
        # because it honours runMode=foreground and would block this request.
        try:
            result = _run(["stop"], timeout, cwd=cwd)
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")
        except subprocess.TimeoutExpired:
            raise HTTPException(status_code=504, detail=f"openacp {action} timed out")

        stop_output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))

        if action == "stop":
            ok = result.returncode == 0
            return DaemonActionResult(
                ok=ok,
                action=action,
                output=stop_output or ("OpenACP stopped" if ok else "OpenACP stop failed"),
                status=read_status(timeout, sessions_path),
            )

        # A failing stop is not fatal on restart — OpenACP may simply be offline.
        time.sleep(STOP_SETTLE_SECONDS)
        try:
            # Not "start": that subcommand always daemonizes, so the new console
            # window would open, print a PID and close again.
            _spawn_foreground(["--foreground"], cwd)
        except FileNotFoundError:
            raise HTTPException(status_code=503, detail="openacp was not found on the backend's PATH")
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Could not start OpenACP: {exc}")

        status = _wait_until_running(timeout, sessions_path)
        message = (
            "OpenACP was started in its own console window."
            if status.running
            else f"OpenACP did not come up within {STARTUP_TIMEOUT_SECONDS}s — check its window."
        )

        return DaemonActionResult(
            ok=status.running,
            action=action,
            output=_truncate("\n".join(part for part in (stop_output, message) if part)),
            status=status,
        )
    finally:
        _action_lock.release()
