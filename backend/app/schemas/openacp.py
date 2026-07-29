from datetime import datetime

from pydantic import BaseModel, model_validator

from ..services.openacp_validation import (
    validate_agent,
    validate_channel_id,
    validate_workspace,
)

__all__ = [
    "AgentRead",
    "DaemonActionResult",
    "DaemonStatusRead",
    "ChannelBindingRead",
    "ChannelBindingWrite",
    "ChannelBindingsRead",
    "ChannelBindingsUpdate",
    "HookStatusRead",
    "InstallResult",
    "InstallStatusRead",
    "InvalidBinding",
    "OpenAcpSessionRead",
    "RedeployResult",
    "SessionActionResult",
    "SettingsTransferResult",
    "SettingsTransferStatus",
]


class ChannelBindingWrite(BaseModel):
    """One project binding submitted by the dashboard.

    Validation mirrors validateChannelBindings() in
    openacp-channel-bindings/src/bindings.ts — the adapter drops entries that
    fail these rules at runtime, so accepting them here would silently produce
    a binding that never works.
    """

    channel_id: str
    agent: str
    workspace: str

    @model_validator(mode="after")
    def check_fields(self) -> "ChannelBindingWrite":
        self.channel_id = validate_channel_id(self.channel_id)
        self.agent = validate_agent(self.agent)
        self.workspace = validate_workspace(self.workspace)
        return self


class ChannelBindingsUpdate(BaseModel):
    bindings: list[ChannelBindingWrite]
    # Optimistic lock: the revision the client last read. Omitted = force write.
    revision: str | None = None

    @model_validator(mode="after")
    def no_duplicate_channels(self) -> "ChannelBindingsUpdate":
        seen: set[str] = set()
        for binding in self.bindings:
            if binding.channel_id in seen:
                raise ValueError(f"duplicate channel id: {binding.channel_id}")
            seen.add(binding.channel_id)
        return self


class ChannelBindingRead(BaseModel):
    channel_id: str
    agent: str
    workspace: str
    # False when the configured directory is gone — the adapter would ignore
    # this binding, so the UI warns before the user tries to save it again.
    workspace_exists: bool
    # The Agent Deck project whose repository_path is this workspace, if any.
    # Resolved on read from the path itself — settings.json stores no id, so
    # there is nothing that can go stale when a project is renamed or deleted.
    project_id: int | None = None
    project_name: str | None = None


class OpenAcpSessionRead(BaseModel):
    """One live OpenACP session — a single Discord thread.

    Read straight from the running server; Agent Deck stores none of this. When
    OpenACP is down there is no history to fall back on.
    """

    id: str
    agent: str
    # First message of the thread, empty while the thread is still nameless.
    name: str = ""
    # "active", "initializing", "finished", "error".
    status: str
    # True while the session still holds an agent process — the states a restart
    # would terminate. Computed here so the dashboard does not have to repeat
    # the status list to decide what is worth killing.
    active: bool = False
    workspace: str = ""
    project_id: int | None = None
    project_name: str | None = None
    created_at: str = ""
    last_active_at: str = ""
    prompt_running: bool = False
    queue_depth: int = 0
    # True when the agent may act without permission prompts.
    dangerous_mode: bool = False


class InvalidBinding(BaseModel):
    """An entry already in settings.json that fails validation.

    Surfaced because the file is hand-editable and these entries are dropped
    on the next save.
    """

    channel_id: str
    reason: str


class ChannelBindingsRead(BaseModel):
    bindings: list[ChannelBindingRead]
    invalid_entries: list[InvalidBinding]
    settings_path: str
    revision: str
    restart_required: bool = False


class AgentRead(BaseModel):
    id: str
    name: str


class HookStatusRead(BaseModel):
    # None = could not be determined (node missing, timeout, script error).
    installed: bool | None
    detail: str
    checked_at: datetime


class RedeployResult(BaseModel):
    ok: bool
    installed: bool | None
    exit_code: int
    output: str
    restart_required: bool = True


class SettingsTransferStatus(BaseModel):
    # The live OpenACP settings.json in the workspace.
    live_exists: bool
    live_path: str
    # The copy kept inside the repo folder for transfer.
    bundle_exists: bool
    bundle_path: str
    # ISO-8601 mtime of the bundle, None when it does not exist yet.
    bundle_modified: str | None = None
    # Whether the bundle carries a non-empty botToken (the value is never
    # returned — only this flag).
    bundle_has_token: bool | None = None


class SettingsTransferResult(BaseModel):
    ok: bool
    # "export" (live -> bundle) or "import" (bundle -> live).
    action: str
    # Destination path written.
    path: str
    # Whether the copied file carries a non-empty botToken.
    has_token: bool
    detail: str = ""


class InstallStatusRead(BaseModel):
    # Whether the "openacp" binary is on the backend's PATH.
    cli_installed: bool
    # Parsed from "openacp --version"; None when the CLI is absent or unreadable.
    cli_version: str | None = None
    # Whether @openacp/discord-adapter is in the global npm tree.
    # None = npm could not be queried (missing, timeout).
    adapter_installed: bool | None = None
    # False when npm itself is missing — nothing can be installed until Node is.
    npm_available: bool = True
    detail: str = ""


class InstallResult(BaseModel):
    ok: bool
    exit_code: int
    output: str
    status: InstallStatusRead


class DaemonStatusRead(BaseModel):
    running: bool
    # "online", "offline", or "unknown" when the CLI could not be reached.
    status: str
    pid: int | None = None
    mode: str | None = None
    channels: list[str] = []
    # Sessions that a restart would terminate.
    active_sessions: int = 0
    # True when OpenACP runs in its own console window instead of as a daemon.
    # "openacp status" cannot see such an instance (no PID file), so it is
    # detected through the daemon API — and it cannot be controlled from here.
    foreground: bool = False
    detail: str = ""


class DaemonActionResult(BaseModel):
    ok: bool
    action: str
    output: str
    status: DaemonStatusRead


class SessionActionResult(BaseModel):
    ok: bool
    session_id: str
