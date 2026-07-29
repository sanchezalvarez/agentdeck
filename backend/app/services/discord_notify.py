"""Posts task summaries to a Discord channel webhook.

A channel webhook URL addresses exactly one channel and carries no bot
identity, so Agent Deck still stores no Discord credentials (see README). The
feature is off whenever AGENT_HUB_DISCORD_SUMMARY_WEBHOOK is empty.

The summary text is whatever the agent itself reported to `agent-report
finish/fail/block` — nothing here writes or rewrites it, so the message says
what the agent that did the work says, whichever agent that was.

Delivery runs on a daemon thread. The lifecycle endpoints are async handlers
calling straight into these sync services, so posting inline would block the
event loop and stall the agent's own finish call behind Discord's latency.
The payload is therefore built by the caller, while its database session is
still open, and the thread only ever sees a plain dict.
"""

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Any, Literal

from ..config import get_settings
from ..models.tables import Task

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
# Discord allows 4096 characters in an embed description; a summary that long
# is unreadable in a channel anyway.
MAX_SUMMARY_CHARS = 1500
MAX_FIELD_CHARS = 1024

NotifyKind = Literal["finished", "failed", "blocked"]

_STYLES: dict[str, tuple[int, str]] = {
    # colour, footer note
    "finished": (0x3BA55D, "waiting for review"),
    "failed": (0xED4245, "failed"),
    "blocked": (0xFAA61A, "blocked — needs input"),
}


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(value.value if hasattr(value, "value") else value)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def build_payload(kind: NotifyKind, task: Task, detail: str | None = None) -> dict[str, Any]:
    """The Discord webhook body for one finished/failed/blocked task.

    Reads the ORM object, so it must run while the caller's session is open.
    """
    colour, footer = _STYLES[kind]

    fields: list[dict[str, Any]] = []
    project = getattr(task, "project", None)
    if project is not None:
        fields.append({"name": "Project", "value": project.name, "inline": True})
    agent = _enum_value(task.agent_type)
    if agent:
        fields.append({"name": "Agent", "value": agent, "inline": True})

    checks = [
        f"{label} {_enum_value(value)}"
        for label, value in (("tests", task.tests_status), ("build", task.build_status))
        if _enum_value(value) not in (None, "not_run")
    ]
    if task.exit_code is not None:
        checks.append(f"exit {task.exit_code}")
    if checks:
        fields.append({"name": "Checks", "value": " · ".join(checks), "inline": True})

    if task.branch:
        commit = f" @ {task.end_commit[:8]}" if task.end_commit else ""
        fields.append({"name": "Branch", "value": _truncate(task.branch + commit, MAX_FIELD_CHARS)})

    return {
        "embeds": [
            {
                "title": _truncate(f"{task.public_id} — {task.title}", 256),
                "description": _truncate(detail or "(no summary reported)", MAX_SUMMARY_CHARS),
                "color": colour,
                "fields": fields,
                "footer": {"text": f"Agent Deck · {footer}"},
            }
        ]
    }


def _post(url: str, payload: dict[str, Any]) -> None:
    request = urllib.request.Request(  # noqa: S310 - fixed https webhook from settings
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):  # noqa: S310
        pass


def _post_quietly(url: str, payload: dict[str, Any]) -> None:
    """A dead webhook must never turn into a failed agent report."""
    try:
        _post(url, payload)
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # The URL is a secret, so only the failure itself is logged.
        logger.warning("Discord summary webhook failed: %s", exc)


def notify_task(kind: NotifyKind, task: Task, detail: str | None = None) -> None:
    """Fire-and-forget: returns before the request is made, and never raises."""
    webhook = get_settings().discord_summary_webhook
    if not webhook:
        return
    payload = build_payload(kind, task, detail)
    threading.Thread(
        target=_post_quietly,
        args=(webhook, payload),
        name=f"discord-notify-{task.public_id}",
        daemon=True,
    ).start()
