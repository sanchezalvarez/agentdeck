from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _openacp_home() -> Path:
    return Path.home() / "openacp-workspace" / ".openacp"


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env files.

    All variables use the AGENT_DECK_ prefix, e.g. AGENT_DECK_PORT=8765.
    """

    model_config = SettingsConfigDict(
        env_prefix="AGENT_DECK_",
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8765
    database_url: str = "sqlite:///./agent_deck.db"
    write_token: str = ""
    cors_origins: str = "http://localhost:3000"
    # Workers whose last heartbeat is older than this are reported as offline/stale.
    worker_stale_seconds: int = 300
    # Discord channel webhook that receives a summary when a task finishes,
    # fails or is blocked. Empty disables the notifications entirely.
    discord_summary_webhook: str = ""

    # --- OpenACP channel bindings -----------------------------------------
    # Plugin settings file of @openacp/discord-adapter. It also contains the
    # Discord bot token, so only the "channelBindings" key is ever exposed.
    openacp_settings_path: str = str(
        _openacp_home() / "plugins" / "data" / "@openacp" / "discord-adapter" / "settings.json"
    )
    openacp_agents_path: str = str(_openacp_home() / "agents.json")
    openacp_sessions_path: str = str(_openacp_home() / "sessions.json")
    # Resolved from this file's location, so renaming or moving the repository
    # folder does not break the default.
    openacp_bindings_module_dir: str = str(
        Path(__file__).resolve().parents[2] / "openacp-channel-bindings"
    )
    # Backups are full copies of the settings file (bot token included), so they
    # deliberately live outside the repository.
    openacp_settings_backup_dir: str = str(Path.home() / ".agent-deck" / "settings-backups")
    openacp_backup_retention: int = 20
    openacp_hook_timeout_seconds: int = 120
    # A global "npm install -g" can pull the network for minutes on a fresh PC.
    openacp_install_timeout_seconds: int = 300
    # Full copy of the OpenACP settings.json (token INCLUDED) kept inside the
    # repo folder so it travels when the folder is copied to another PC. The
    # directory is gitignored — it must never be committed.
    openacp_settings_export_path: str = str(
        Path(__file__).resolve().parents[2] / "openacp-config" / "settings.json"
    )

    # --- Screenshots ------------------------------------------------------
    # Where captured PNGs are written (relative to backend/, like the SQLite db).
    screenshot_dir: str = "./screenshots"
    # "pip install mss" into the backend venv.
    screenshot_install_timeout_seconds: int = 180

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
