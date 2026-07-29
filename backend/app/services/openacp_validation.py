"""Validation rules for OpenACP channel bindings.

These mirror validateChannelBindings() in
openacp-channel-bindings/src/bindings.ts. The adapter silently drops entries
that fail them at runtime, so the two implementations must stay in sync —
change one, change the other.
"""

import re
from pathlib import Path

SNOWFLAKE_RE = r"\d{17,20}"
_SNOWFLAKE = re.compile(rf"^{SNOWFLAKE_RE}$")


def is_snowflake(value: str) -> bool:
    return bool(_SNOWFLAKE.match(value))


def is_unc_path(value: str) -> bool:
    """UNC paths are rejected: an unreachable host makes Path.is_dir() block
    for tens of seconds, which would stall the request."""
    return value.startswith("\\\\") or value.startswith("//")


def workspace_exists(value: str) -> bool:
    if not value or is_unc_path(value):
        return False
    try:
        return Path(value).is_dir()
    except OSError:
        return False


def validate_channel_id(value: str) -> str:
    value = value.strip()
    if not is_snowflake(value):
        raise ValueError("channel id must be a numeric discord snowflake (17-20 digits)")
    return value


def validate_agent(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("agent must not be empty")
    return value


def validate_workspace(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("workspace must not be empty")
    if is_unc_path(value):
        raise ValueError("unc network paths are not supported as a workspace")
    if not workspace_exists(value):
        raise ValueError(f"workspace directory does not exist: {value}")
    return value


def describe_structural_problem(channel_id: str, value: object) -> str | None:
    """Non-raising check used when reading existing entries from disk.

    Returns a reason string when the entry is structurally broken, or None when
    it is well-formed. A missing workspace directory is NOT structural — such a
    binding is returned with workspace_exists=False so the UI can warn instead
    of hiding it.
    """
    if not is_snowflake(channel_id):
        return "channel id must be a numeric discord snowflake (17-20 digits)"
    if not isinstance(value, dict):
        return 'binding must be an object with "agent" and "workspace"'
    agent = value.get("agent")
    workspace = value.get("workspace")
    if not isinstance(agent, str) or not agent.strip():
        return '"agent" must be a non-empty string'
    if not isinstance(workspace, str) or not workspace.strip():
        return '"workspace" must be a non-empty string'
    return None
