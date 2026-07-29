"""Read/write access to the @openacp/discord-adapter plugin settings file.

SECURITY: that file also contains the Discord bot token. Two rules hold
everywhere in this module:

  1. Never return, log or embed the parsed settings dict (or any exception text
     derived from parsing it) in an API response. Error details are fixed
     strings.
  2. Writes mutate only the "channelBindings" key of the freshly parsed file.
     The rest of the document is never rebuilt from client input.
"""

import json
import os
import shutil
import tempfile
import threading
import time
from datetime import datetime, timezone
from collections.abc import Iterable
from pathlib import Path
from typing import Any, TypeVar

from fastapi import HTTPException

from ..schemas.openacp import (
    AgentRead,
    ChannelBindingRead,
    ChannelBindingWrite,
    InvalidBinding,
)
from .openacp_validation import describe_structural_problem, workspace_exists

BINDINGS_KEY = "channelBindings"

# Any row exposing workspace / project_id / project_name — see pair_with_projects.
RowT = TypeVar("RowT")

# Serialises the read-modify-write cycle so two concurrent saves cannot
# interleave their backup/replace steps.
_write_lock = threading.Lock()


# --- reading ---------------------------------------------------------------


def _settings_file(path: str) -> Path:
    return Path(path)


def read_settings(path: str) -> dict[str, Any]:
    """Parse the settings file. Never leaks file content into the error."""
    file = _settings_file(path)
    try:
        raw = file.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="OpenACP settings file not found")
    except OSError:
        raise HTTPException(status_code=503, detail="OpenACP settings file could not be read")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # The decoder's message quotes surrounding characters — and botToken is
        # the first key in the file. Never forward it.
        raise HTTPException(status_code=503, detail="OpenACP settings file is not valid JSON")

    if not isinstance(data, dict):
        raise HTTPException(status_code=503, detail="OpenACP settings file must contain a JSON object")
    return data


def compute_revision(path: str) -> str:
    """Cheap optimistic-lock token derived from the file's mtime and size."""
    try:
        stat = _settings_file(path).stat()
    except OSError:
        raise HTTPException(status_code=503, detail="OpenACP settings file not found")
    return f"{stat.st_mtime_ns}-{stat.st_size}"


def read_channel_bindings(path: str) -> tuple[list[ChannelBindingRead], list[InvalidBinding]]:
    data = read_settings(path)
    raw = data.get(BINDINGS_KEY)

    bindings: list[ChannelBindingRead] = []
    invalid: list[InvalidBinding] = []

    if raw is None:
        return bindings, invalid
    if not isinstance(raw, dict):
        invalid.append(InvalidBinding(channel_id="<root>", reason="channelBindings must be a JSON object"))
        return bindings, invalid

    for channel_id, value in raw.items():
        problem = describe_structural_problem(channel_id, value)
        if problem:
            invalid.append(InvalidBinding(channel_id=channel_id, reason=problem))
            continue
        workspace = value["workspace"].strip()
        bindings.append(
            ChannelBindingRead(
                channel_id=channel_id,
                agent=value["agent"].strip(),
                workspace=workspace,
                workspace_exists=workspace_exists(workspace),
            )
        )

    bindings.sort(key=lambda b: b.channel_id)
    return bindings, invalid


def pair_with_projects(rows: list[RowT], projects: Iterable[Any]) -> list[RowT]:
    """Links each row to the Agent Hub project living at its workspace.

    Works on anything carrying workspace / project_id / project_name: channel
    bindings and live sessions both do.

    The path is the only join key. settings.json deliberately stores no project
    id: it stays portable, and a renamed or deleted project cannot leave a
    dangling reference in OpenACP's own configuration.

    Paths are compared with normcase + normpath, so C:\\Unity\\X and
    c:/unity/x/ match on Windows. Projects without a repository_path are
    skipped, and the first project wins if two share a path.
    """
    by_path: dict[str, Any] = {}
    for project in projects:
        path = getattr(project, "repository_path", None)
        if path:
            by_path.setdefault(os.path.normcase(os.path.normpath(path.strip())), project)

    for row in rows:
        if not row.workspace:
            continue
        match = by_path.get(os.path.normcase(os.path.normpath(row.workspace.strip())))
        if match is not None:
            row.project_id = match.id
            row.project_name = match.name

    return rows


def read_agents(path: str) -> list[AgentRead]:
    """Available agents from agents.json. A missing file is not an error —
    the agent field falls back to free text in the UI."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []

    installed = data.get("installed") if isinstance(data, dict) else None
    if not isinstance(installed, dict):
        return []

    agents = [
        AgentRead(id=key, name=(value.get("name") or key) if isinstance(value, dict) else key)
        for key, value in installed.items()
    ]
    agents.sort(key=lambda a: a.id)
    return agents


# --- writing ---------------------------------------------------------------


def _make_backup(file: Path, backup_dir: str, revision: str, retention: int) -> None:
    directory = Path(backup_dir)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    # The revision disambiguates two saves within the same second.
    target = directory / f"settings-{stamp}-{revision}.json"
    shutil.copy2(file, target)

    backups = sorted(directory.glob("settings-*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in backups[retention:]:
        try:
            stale.unlink()
        except OSError:
            pass


def _atomic_write(file: Path, payload: str) -> None:
    """Write via a temp file in the SAME directory, then os.replace.

    Same directory is mandatory: os.replace across volumes fails on Windows.
    The temp file holds the bot token, so it is unlinked on every failure path.
    """
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=file.parent,
        prefix=".settings-",
        suffix=".tmp",
        delete=False,
    )
    tmp_path = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

        # A running OpenACP, an antivirus or the search indexer can hold a
        # transient handle on the target.
        last_error: OSError | None = None
        for attempt in range(3):
            try:
                os.replace(tmp_path, file)
                return
            except PermissionError as err:
                last_error = err
                time.sleep(0.1 * (attempt + 1))
        raise HTTPException(
            status_code=503,
            detail="Could not replace the settings file — it is locked by another process. Stop OpenACP and retry.",
        ) from last_error
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def write_channel_bindings(
    path: str,
    backup_dir: str,
    retention: int,
    rows: list[ChannelBindingWrite],
    expected_revision: str | None,
) -> str:
    """Replace channelBindings, preserving every other key. Returns the new revision."""
    file = _settings_file(path)

    with _write_lock:
        # Re-read inside the lock so the revision check and the write see the
        # same state.
        data = read_settings(path)
        current_revision = compute_revision(path)

        if expected_revision is not None and expected_revision != current_revision:
            raise HTTPException(
                status_code=409,
                detail="Settings file changed on disk since it was loaded — reload and try again",
            )

        # Mutate only this key on the already-parsed document.
        data[BINDINGS_KEY] = {
            row.channel_id: {"agent": row.agent, "workspace": row.workspace} for row in rows
        }

        payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

        _make_backup(file, backup_dir, current_revision, retention)
        _atomic_write(file, payload)

        return compute_revision(path)
