import urllib.error

import pytest

from app.config import get_settings
from app.services import discord_notify

WEBHOOK = "https://discord.test/api/webhooks/1/abc"


class InlineThread:
    """Runs the delivery on the calling thread so tests stay deterministic."""

    def __init__(self, target, args, **_kwargs):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


@pytest.fixture
def webhook(monkeypatch):
    """Enables the webhook. Returns the list of deliveries the backend made."""
    sent: list[dict] = []

    def enable(poster=None):
        monkeypatch.setattr(get_settings(), "discord_summary_webhook", WEBHOOK)
        monkeypatch.setattr(discord_notify.threading, "Thread", InlineThread)

        def capture(url, payload):
            sent.append({"url": url, "payload": payload})

        monkeypatch.setattr(discord_notify, "_post", poster or capture)
        return sent

    return enable


def finish(client, auth, task, **overrides):
    body = {"summary": "Rewrote the table parser and added 12 tests.", **overrides}
    return client.post(f"/api/tasks/{task['public_id']}/finish", json=body, headers=auth)


def test_nothing_is_sent_while_no_webhook_is_configured(client, auth, task, monkeypatch):
    calls: list = []
    monkeypatch.setattr(discord_notify, "_post", lambda url, payload: calls.append(url))

    assert finish(client, auth, task).status_code == 200
    assert calls == []


def test_finish_posts_the_agents_own_summary(client, auth, task, webhook):
    sent = webhook()

    assert finish(client, auth, task, branch="agent/rem-1-docx", commit="a94c2e1f9",
                  tests="passed", build="passed").status_code == 200

    assert len(sent) == 1
    assert sent[0]["url"] == WEBHOOK
    embed = sent[0]["payload"]["embeds"][0]
    assert embed["title"].startswith(task["public_id"])
    assert embed["description"] == "Rewrote the table parser and added 12 tests."
    assert embed["color"] == 0x3BA55D
    assert "review" in embed["footer"]["text"]

    fields = {f["name"]: f["value"] for f in embed["fields"]}
    assert fields["Project"] == "CrowForge"
    assert fields["Agent"] == "claude"
    assert fields["Checks"] == "tests passed · build passed"
    # The commit is shortened — a full hash tells the reader nothing extra.
    assert fields["Branch"] == "agent/rem-1-docx @ a94c2e1f"


def test_fail_posts_the_error(client, auth, task, webhook):
    sent = webhook()

    response = client.post(
        f"/api/tasks/{task['public_id']}/fail",
        json={"error": "Backend tests failed.", "tests": "failed", "exit_code": 1},
        headers=auth,
    )

    assert response.status_code == 200
    embed = sent[0]["payload"]["embeds"][0]
    assert embed["description"] == "Backend tests failed."
    assert embed["color"] == 0xED4245
    assert "tests failed" in {f["name"]: f["value"] for f in embed["fields"]}["Checks"]


def test_block_posts_the_reason(client, auth, task, webhook):
    """The reason lives only on the event row, so it has to be passed explicitly."""
    sent = webhook()

    response = client.post(
        f"/api/tasks/{task['public_id']}/block",
        json={"reason": "Missing the client test document."},
        headers=auth,
    )

    assert response.status_code == 200
    embed = sent[0]["payload"]["embeds"][0]
    assert embed["description"] == "Missing the client test document."
    assert embed["color"] == 0xFAA61A


def test_a_dead_webhook_never_fails_the_agents_report(client, auth, task, webhook):
    def explode(url, payload):
        raise urllib.error.URLError("connection refused")

    webhook(poster=explode)

    # The agent must still see its finish succeed — Discord is not in that path.
    assert finish(client, auth, task).status_code == 200


def test_an_overlong_summary_is_truncated(client, auth, task, webhook):
    sent = webhook()

    assert finish(client, auth, task, summary="x" * 5000).status_code == 200

    description = sent[0]["payload"]["embeds"][0]["description"]
    assert len(description) == discord_notify.MAX_SUMMARY_CHARS
    assert description.endswith("…")
