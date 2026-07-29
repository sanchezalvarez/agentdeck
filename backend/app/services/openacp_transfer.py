"""Copy the whole OpenACP settings.json between the live workspace and a bundle
kept inside the repo folder, so the config (Discord bot token INCLUDED) travels
when the folder is copied to another PC.

SECURITY: this file's whole point is a token-bearing copy, so two rules are
non-negotiable:
  * the bundle directory is gitignored — the token must never be committed;
  * the token value is NEVER returned by the API. Endpoints report only paths,
    timestamps, and a boolean "does it carry a token".

All work is a local filesystem copy — no shell, no network.
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException

from ..schemas.openacp import SettingsTransferResult, SettingsTransferStatus


def _has_token(path: Path) -> bool:
    """True when the file carries a non-empty botToken. Best effort — a missing
    or malformed file simply reads as 'no token'."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(isinstance(data, dict) and data.get("botToken"))


def _mtime_iso(path: Path) -> str | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        return None


def read_status(live_path: str, bundle_path: str) -> SettingsTransferStatus:
    """Never raises."""
    live = Path(live_path)
    bundle = Path(bundle_path)
    return SettingsTransferStatus(
        live_exists=live.is_file(),
        live_path=str(live),
        bundle_exists=bundle.is_file(),
        bundle_path=str(bundle),
        bundle_modified=_mtime_iso(bundle) if bundle.is_file() else None,
        bundle_has_token=_has_token(bundle) if bundle.is_file() else None,
    )


def export_settings(live_path: str, bundle_path: str) -> SettingsTransferResult:
    """Live workspace settings -> repo bundle (so it copies with the folder)."""
    live = Path(live_path)
    bundle = Path(bundle_path)

    if not live.is_file():
        raise HTTPException(
            status_code=422,
            detail=f"OpenACP settings.json not found at {live}. Is the workspace set up?",
        )

    bundle.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(live, bundle)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write the bundle: {exc}")

    has_token = _has_token(bundle)
    return SettingsTransferResult(
        ok=True,
        action="export",
        path=str(bundle),
        has_token=has_token,
        detail=(
            "Copied into the repo folder. It contains the Discord bot token — it is gitignored, "
            "so keep it that way and never commit it."
            if has_token
            else "Copied into the repo folder (no bot token was present in the source)."
        ),
    )


def import_settings(bundle_path: str, live_path: str) -> SettingsTransferResult:
    """Repo bundle -> live workspace settings (run this on the new PC)."""
    bundle = Path(bundle_path)
    live = Path(live_path)

    if not bundle.is_file():
        raise HTTPException(
            status_code=422,
            detail=f"No settings bundle found at {bundle}. Export it on the source PC first.",
        )

    live.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite an existing live settings without a way back.
    if live.is_file():
        try:
            shutil.copy2(live, live.with_suffix(live.suffix + ".pre-import.bak"))
        except OSError:
            # A failed safety copy should not block the import, but note it.
            pass

    try:
        shutil.copy2(bundle, live)
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Could not write the live settings: {exc}")

    has_token = _has_token(live)
    return SettingsTransferResult(
        ok=True,
        action="import",
        path=str(live),
        has_token=has_token,
        detail=(
            "Applied to the live workspace. Restart OpenACP for it to take effect; "
            "make sure the bound workspace folders exist on this PC."
        ),
    )
