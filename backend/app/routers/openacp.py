from anyio import to_thread
from fastapi import APIRouter
from sqlmodel import Session, select

from ..config import get_settings
from ..dependencies import SessionDep, WriteAuth
from ..models.tables import Project
from ..schemas.openacp import (
    AgentRead,
    ChannelBindingsRead,
    ChannelBindingsUpdate,
    DaemonActionResult,
    DaemonStatusRead,
    HookStatusRead,
    InstallResult,
    InstallStatusRead,
    OpenAcpSessionRead,
    RedeployResult,
    SessionActionResult,
    SettingsTransferResult,
    SettingsTransferStatus,
)
from ..services import (
    openacp_daemon,
    openacp_hook,
    openacp_install,
    openacp_settings,
    openacp_transfer,
)
from ..services.broadcaster import broadcaster

router = APIRouter(prefix="/openacp", tags=["openacp"])


# --- Channel bindings ------------------------------------------------------


def _all_projects(session: Session) -> list[Project]:
    """Inactive projects included: a binding pointing at one should still show
    the project's name rather than look unlinked."""
    return list(session.exec(select(Project)).all())


@router.get("/channel-bindings", response_model=ChannelBindingsRead)
async def get_channel_bindings(session: SessionDep) -> ChannelBindingsRead:
    """Returns only the channelBindings key — never the bot token."""
    settings = get_settings()
    bindings, invalid = openacp_settings.read_channel_bindings(settings.openacp_settings_path)
    return ChannelBindingsRead(
        bindings=openacp_settings.pair_with_projects(bindings, _all_projects(session)),
        invalid_entries=invalid,
        settings_path=settings.openacp_settings_path,
        revision=openacp_settings.compute_revision(settings.openacp_settings_path),
        restart_required=False,
    )


@router.patch("/channel-bindings", response_model=ChannelBindingsRead, dependencies=[WriteAuth])
async def update_channel_bindings(
    payload: ChannelBindingsUpdate, session: SessionDep
) -> ChannelBindingsRead:
    settings = get_settings()
    revision = openacp_settings.write_channel_bindings(
        settings.openacp_settings_path,
        settings.openacp_settings_backup_dir,
        settings.openacp_backup_retention,
        payload.bindings,
        payload.revision,
    )
    bindings, invalid = openacp_settings.read_channel_bindings(settings.openacp_settings_path)

    # Count only — workspace paths are not broadcast to SSE subscribers.
    broadcaster.publish("channel_bindings_saved", {"count": len(bindings)})

    return ChannelBindingsRead(
        bindings=openacp_settings.pair_with_projects(bindings, _all_projects(session)),
        invalid_entries=invalid,
        settings_path=settings.openacp_settings_path,
        revision=revision,
        restart_required=True,
    )


@router.get("/agents", response_model=list[AgentRead])
async def list_agents() -> list[AgentRead]:
    return openacp_settings.read_agents(get_settings().openacp_agents_path)


# --- Settings transfer (move to another PC) --------------------------------


@router.get("/settings/transfer-status", response_model=SettingsTransferStatus)
async def settings_transfer_status() -> SettingsTransferStatus:
    """Whether a settings bundle exists in the repo folder, and when it was made.

    Never returns the bot token — only paths, a timestamp, and a has-token flag.
    """
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_transfer.read_status,
        settings.openacp_settings_path,
        settings.openacp_settings_export_path,
    )


@router.post("/settings/export", response_model=SettingsTransferResult, dependencies=[WriteAuth])
async def settings_export() -> SettingsTransferResult:
    """Copies the live settings.json (bot token included) into the gitignored
    repo bundle so it travels when the folder is copied to another PC."""
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_transfer.export_settings,
        settings.openacp_settings_path,
        settings.openacp_settings_export_path,
    )


@router.post("/settings/import", response_model=SettingsTransferResult, dependencies=[WriteAuth])
async def settings_import() -> SettingsTransferResult:
    """Applies the repo bundle to the live workspace (run this on the new PC).
    The previous live file is kept as a .pre-import.bak."""
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_transfer.import_settings,
        settings.openacp_settings_export_path,
        settings.openacp_settings_path,
    )


# --- Installation ----------------------------------------------------------


@router.get("/install-status", response_model=InstallStatusRead)
async def get_install_status() -> InstallStatusRead:
    """Whether the OpenACP CLI + Discord adapter are installed on this PC.

    Lets a freshly copied checkout install OpenACP from the dashboard instead of
    the npm command line. Read-only, so no auth in V1.
    """
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_install.read_status,
        settings.openacp_hook_timeout_seconds,
    )


@router.post("/install", response_model=InstallResult, dependencies=[WriteAuth])
async def install_openacp() -> InstallResult:
    """Installs @openacp/cli + @openacp/discord-adapter globally via npm.

    Does not touch the OpenACP workspace or Discord bot token — those stay
    machine-specific and manual.
    """
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_install.run_install,
        settings.openacp_install_timeout_seconds,
    )


# --- Hook ------------------------------------------------------------------


@router.get("/hook-status", response_model=HookStatusRead)
async def get_hook_status() -> HookStatusRead:
    settings = get_settings()
    # Threaded: subprocess.run would otherwise block the event loop and the SSE stream.
    return await to_thread.run_sync(
        openacp_hook.check_hook,
        settings.openacp_bindings_module_dir,
        settings.openacp_hook_timeout_seconds,
    )


@router.post("/redeploy", response_model=RedeployResult, dependencies=[WriteAuth])
async def redeploy_hook() -> RedeployResult:
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_hook.run_redeploy,
        settings.openacp_bindings_module_dir,
        settings.openacp_hook_timeout_seconds,
    )


# --- Daemon ----------------------------------------------------------------


@router.get("/daemon-status", response_model=DaemonStatusRead)
async def get_daemon_status() -> DaemonStatusRead:
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_daemon.read_status,
        settings.openacp_hook_timeout_seconds,
        settings.openacp_sessions_path,
    )


@router.get("/sessions", response_model=list[OpenAcpSessionRead])
async def list_sessions(session: SessionDep) -> list[OpenAcpSessionRead]:
    """Live sessions, paired with projects by workspace path.

    Empty when OpenACP is down — check /daemon-status to tell that apart from
    genuinely having nothing running.
    """
    settings = get_settings()
    sessions = await to_thread.run_sync(
        openacp_daemon.read_sessions,
        settings.openacp_hook_timeout_seconds,
    )
    return openacp_settings.pair_with_projects(sessions, _all_projects(session))


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=SessionActionResult,
    dependencies=[WriteAuth],
)
async def cancel_session(session_id: str) -> SessionActionResult:
    """Cancels one OpenACP session.

    Deleting a Discord thread does not stop its session — OpenACP is never told
    about the deletion. This is the manual kill switch for such zombies.
    """
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_daemon.cancel_session,
        session_id,
        settings.openacp_hook_timeout_seconds,
    )


@router.post("/daemon/restart", response_model=DaemonActionResult, dependencies=[WriteAuth])
async def restart_daemon() -> DaemonActionResult:
    """Restarts OpenACP so configuration changes take effect.

    Terminates running agent sessions — the dashboard confirms first.
    """
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_daemon.run_action,
        "restart",
        settings.openacp_hook_timeout_seconds,
        settings.openacp_sessions_path,
        settings.openacp_scripts_dir,
        settings.openacp_foreground_action_timeout_seconds,
    )


@router.post("/daemon/stop", response_model=DaemonActionResult, dependencies=[WriteAuth])
async def stop_daemon() -> DaemonActionResult:
    settings = get_settings()
    return await to_thread.run_sync(
        openacp_daemon.run_action,
        "stop",
        settings.openacp_hook_timeout_seconds,
        settings.openacp_sessions_path,
        settings.openacp_scripts_dir,
        settings.openacp_foreground_action_timeout_seconds,
    )
