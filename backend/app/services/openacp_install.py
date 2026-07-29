"""Install the OpenACP CLI and Discord adapter globally through npm.

SECURITY: like openacp_daemon and openacp_hook, every call here is a fixed
argument list with shell=False and no user-supplied input. The only command
that ever runs is a global npm install of two hard-coded package names.

This exists so a fresh PC can get OpenACP from the dashboard instead of having
to remember the npm command. It does NOT configure the OpenACP workspace or the
Discord bot token — those are machine-specific and stay manual.
"""

import re
import shutil
import subprocess
import threading

from fastapi import HTTPException

from ..schemas.openacp import InstallResult, InstallStatusRead

# The two packages OpenACP is made of: the CLI binary and the Discord adapter
# plugin. Both are pinned by name only — npm resolves the latest published
# version, matching how they were installed originally.
CLI_PACKAGE = "@openacp/cli"
ADAPTER_PACKAGE = "@openacp/discord-adapter"

MAX_OUTPUT_CHARS = 8192

# "openacp --version" prints e.g. "openacp v2026.518.2".
_VERSION_RE = re.compile(r"v?(\d+\.\d+\.\d+\S*)")

# A global npm install writes into one shared prefix; two at once would clash.
_install_lock = threading.Lock()


def _truncate(text: str) -> str:
    text = (text or "").strip()
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n… output truncated"


def _npm_path() -> str | None:
    # On Windows this resolves to npm.CMD, which subprocess runs directly
    # (same as openacp.CMD in openacp_daemon).
    return shutil.which("npm")


def _openacp_path() -> str | None:
    return shutil.which("openacp")


def _cli_version(timeout: int) -> str | None:
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
            [_openacp_path(), "--version"],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    match = _VERSION_RE.search((result.stdout or "") + (result.stderr or ""))
    return match.group(1) if match else None


def _adapter_installed(npm: str, timeout: int) -> bool | None:
    """Best effort — None when npm cannot answer.

    "npm ls -g <pkg>" exits 0 when the package is present in the global tree
    and non-zero when it is missing.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
            [npm, "ls", "-g", "--depth=0", ADAPTER_PACKAGE],
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    return result.returncode == 0


def read_status(timeout: int) -> InstallStatusRead:
    """Never raises — a missing npm/openacp is reported, not thrown."""
    npm = _npm_path()
    cli_installed = _openacp_path() is not None

    if not npm:
        return InstallStatusRead(
            cli_installed=cli_installed,
            cli_version=_cli_version(timeout) if cli_installed else None,
            adapter_installed=None,
            npm_available=False,
            detail="npm was not found on the backend's PATH. Install Node.js 20+ first.",
        )

    if not cli_installed:
        return InstallStatusRead(
            cli_installed=False,
            cli_version=None,
            adapter_installed=_adapter_installed(npm, timeout),
            npm_available=True,
            detail="OpenACP is not installed. Click Install to add it globally via npm.",
        )

    return InstallStatusRead(
        cli_installed=True,
        cli_version=_cli_version(timeout),
        adapter_installed=_adapter_installed(npm, timeout),
        npm_available=True,
        detail="OpenACP is installed.",
    )


def run_install(timeout: int) -> InstallResult:
    """Installs (or updates to latest) the CLI and Discord adapter globally.

    Idempotent: running it when they are already present re-resolves them to the
    latest published version, which is harmless.
    """
    npm = _npm_path()
    if not npm:
        raise HTTPException(
            status_code=422,
            detail="npm was not found on the backend's PATH. Install Node.js 20+ first.",
        )

    if not _install_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="An OpenACP install is already running")

    try:
        try:
            result = subprocess.run(  # noqa: S603 - fixed argv, shell=False, no user input
                [npm, "install", "-g", CLI_PACKAGE, ADAPTER_PACKAGE],
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
        except FileNotFoundError:
            raise HTTPException(status_code=422, detail="npm was not found on the backend's PATH")
        except subprocess.TimeoutExpired:
            raise HTTPException(
                status_code=504,
                detail=f"npm install timed out after {timeout}s — it may still be running.",
            )

        output = _truncate("\n".join(part for part in (result.stdout, result.stderr) if part))
        ok = result.returncode == 0

        return InstallResult(
            ok=ok,
            exit_code=result.returncode,
            output=output or ("OpenACP installed" if ok else "npm install failed"),
            # Re-read so the UI shows the freshly installed version without a
            # separate round trip.
            status=read_status(timeout),
        )
    finally:
        _install_lock.release()
