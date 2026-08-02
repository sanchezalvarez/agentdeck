import json
import subprocess
from pathlib import Path

import pytest

from app.config import get_settings
from app.services import openacp_daemon, openacp_hook, openacp_install

# Fabricated fixtures — shaped like Discord snowflakes/tokens, but not real IDs.
BOT_TOKEN = "MTAwMDAwMDAwMDAwMDAwMDAw.GtEsT0.example-token-not-real"

BASE_SETTINGS = {
    "botToken": BOT_TOKEN,
    "guildId": "100000000000000001",
    "forumChannelId": "100000000000000002",
    "notificationChannelId": "100000000000000003",
    "assistantThreadId": "100000000000000004",
}

AGENTS_JSON = {
    "version": 1,
    "installed": {
        "claude": {"name": "Claude Agent", "version": "0.59.0"},
        "codex": {"name": "Codex", "version": "1.1.4"},
    },
}

CHANNEL_A = "111111111111111111"
CHANNEL_B = "222222222222222222"


@pytest.fixture
def openacp_env(tmp_path, monkeypatch):
    """Fake OpenACP layout. Note: no channelBindings key — that mirrors the
    real file, where the key only appears after the first save."""
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps(BASE_SETTINGS, indent=2) + "\n", encoding="utf-8")

    agents_file = tmp_path / "agents.json"
    agents_file.write_text(json.dumps(AGENTS_JSON), encoding="utf-8")

    workspace_a = tmp_path / "ProjectA"
    workspace_b = tmp_path / "ProjectB"
    workspace_a.mkdir()
    workspace_b.mkdir()

    backup_dir = tmp_path / "backups"
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    for name in ("restart-openacp.ps1", "stop-openacp.ps1"):
        (scripts_dir / name).write_text("# fake", encoding="utf-8")
    module_dir = tmp_path / "module"
    (module_dir / "scripts").mkdir(parents=True)
    (module_dir / "dist").mkdir()
    (module_dir / "scripts" / "install-hook.mjs").write_text("// fake", encoding="utf-8")
    (module_dir / "dist" / "index.js").write_text("// fake", encoding="utf-8")

    sessions_file = tmp_path / "sessions.json"
    sessions_file.write_text(
        json.dumps(
            {
                "version": 1,
                "sessions": [
                    {"sessionId": "A", "status": "active"},
                    {"sessionId": "B", "status": "initializing"},
                    {"sessionId": "C", "status": "finished"},
                ],
            }
        ),
        encoding="utf-8",
    )

    settings = get_settings()
    monkeypatch.setattr(settings, "openacp_settings_path", str(settings_file))
    monkeypatch.setattr(settings, "openacp_agents_path", str(agents_file))
    monkeypatch.setattr(settings, "openacp_sessions_path", str(sessions_file))
    monkeypatch.setattr(settings, "openacp_settings_backup_dir", str(backup_dir))
    monkeypatch.setattr(settings, "openacp_bindings_module_dir", str(module_dir))
    monkeypatch.setattr(settings, "openacp_scripts_dir", str(scripts_dir))
    monkeypatch.setattr(settings, "openacp_backup_retention", 20)

    return {
        "settings_file": settings_file,
        "agents_file": agents_file,
        "sessions_file": sessions_file,
        "backup_dir": backup_dir,
        "module_dir": module_dir,
        "scripts_dir": scripts_dir,
        "workspace_a": str(workspace_a),
        "workspace_b": str(workspace_b),
        "missing": str(tmp_path / "Gone"),
    }


def read_file(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_revision(client) -> str:
    return client.get("/api/openacp/channel-bindings").json()["revision"]


def binding(channel_id: str, workspace: str, agent: str = "claude") -> dict:
    return {"channel_id": channel_id, "agent": agent, "workspace": workspace}


# --- project pairing -------------------------------------------------------


def test_binding_is_paired_with_project_by_path(client, auth, openacp_env):
    """The workspace path is the only link between a Discord channel and an
    Agent Deck project — settings.json stores no project id."""
    client.post(
        "/api/projects",
        json={"name": "TheLosers", "repository_path": openacp_env["workspace_a"]},
        headers=auth,
    )
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )

    row = client.get("/api/openacp/channel-bindings").json()["bindings"][0]
    assert row["project_name"] == "TheLosers"
    assert row["project_id"] is not None


def test_pairing_ignores_case_and_separators(client, auth, openacp_env):
    """Windows paths reach us in whatever shape the user typed."""
    noisy = openacp_env["workspace_a"].upper().replace("\\", "/") + "/"
    client.post(
        "/api/projects", json={"name": "Noisy", "repository_path": noisy}, headers=auth
    )
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )

    row = client.get("/api/openacp/channel-bindings").json()["bindings"][0]
    assert row["project_name"] == "Noisy"


def test_binding_without_matching_project_stays_unlinked(client, auth, openacp_env):
    client.post(
        "/api/projects",
        json={"name": "Elsewhere", "repository_path": openacp_env["workspace_b"]},
        headers=auth,
    )
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )

    row = client.get("/api/openacp/channel-bindings").json()["bindings"][0]
    assert row["project_id"] is None
    assert row["project_name"] is None


def test_project_without_repository_path_does_not_break_pairing(client, auth, openacp_env):
    client.post("/api/projects", json={"name": "No path"}, headers=auth)
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )

    assert client.get("/api/openacp/channel-bindings").status_code == 200


# --- reading ---------------------------------------------------------------


def test_get_bindings_when_key_absent(client, openacp_env):
    response = client.get("/api/openacp/channel-bindings")
    assert response.status_code == 200
    body = response.json()
    assert body["bindings"] == []
    assert body["invalid_entries"] == []
    assert body["restart_required"] is False


def test_get_bindings_never_exposes_token(client, openacp_env):
    """The single most important test in this feature."""
    response = client.get("/api/openacp/channel-bindings")
    assert response.status_code == 200
    assert BOT_TOKEN not in response.text
    assert "botToken" not in response.text


def test_get_bindings_returns_existing_entries(client, openacp_env):
    data = read_file(openacp_env["settings_file"])
    data["channelBindings"] = {
        CHANNEL_A: {"agent": "claude", "workspace": openacp_env["workspace_a"]},
    }
    openacp_env["settings_file"].write_text(json.dumps(data, indent=2), encoding="utf-8")

    body = client.get("/api/openacp/channel-bindings").json()
    assert len(body["bindings"]) == 1
    assert body["bindings"][0]["channel_id"] == CHANNEL_A
    assert body["bindings"][0]["workspace_exists"] is True


def test_missing_workspace_reported_not_hidden(client, openacp_env):
    data = read_file(openacp_env["settings_file"])
    data["channelBindings"] = {CHANNEL_A: {"agent": "claude", "workspace": openacp_env["missing"]}}
    openacp_env["settings_file"].write_text(json.dumps(data, indent=2), encoding="utf-8")

    body = client.get("/api/openacp/channel-bindings").json()
    assert body["bindings"][0]["workspace_exists"] is False
    assert body["invalid_entries"] == []


def test_invalid_existing_entries_reported(client, openacp_env):
    data = read_file(openacp_env["settings_file"])
    data["channelBindings"] = {
        "not-a-snowflake": {"agent": "claude", "workspace": openacp_env["workspace_a"]},
        CHANNEL_A: {"agent": "", "workspace": openacp_env["workspace_a"]},
        CHANNEL_B: {"agent": "claude", "workspace": openacp_env["workspace_b"]},
    }
    openacp_env["settings_file"].write_text(json.dumps(data, indent=2), encoding="utf-8")

    body = client.get("/api/openacp/channel-bindings").json()
    assert len(body["bindings"]) == 1
    assert body["bindings"][0]["channel_id"] == CHANNEL_B
    assert {e["channel_id"] for e in body["invalid_entries"]} == {"not-a-snowflake", CHANNEL_A}


def test_missing_settings_file_returns_503(client, openacp_env):
    openacp_env["settings_file"].unlink()
    response = client.get("/api/openacp/channel-bindings")
    assert response.status_code == 503
    assert BOT_TOKEN not in response.text


def test_malformed_json_returns_503_without_leaking(client, openacp_env):
    openacp_env["settings_file"].write_text(
        '{"botToken": "' + BOT_TOKEN + '", oops', encoding="utf-8"
    )
    response = client.get("/api/openacp/channel-bindings")
    assert response.status_code == 503
    assert BOT_TOKEN not in response.text


# --- writing ---------------------------------------------------------------


def test_patch_preserves_other_keys(client, auth, openacp_env):
    revision = get_revision(client)
    response = client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])], "revision": revision},
        headers=auth,
    )
    assert response.status_code == 200, response.text
    assert response.json()["restart_required"] is True

    on_disk = read_file(openacp_env["settings_file"])
    for key, value in BASE_SETTINGS.items():
        assert on_disk[key] == value
    assert on_disk["channelBindings"] == {
        CHANNEL_A: {"agent": "claude", "workspace": openacp_env["workspace_a"]}
    }


def test_patch_requires_write_token(client, openacp_env):
    response = client.patch("/api/openacp/channel-bindings", json={"bindings": []})
    assert response.status_code == 401


def test_patch_creates_backup(client, auth, openacp_env):
    original = openacp_env["settings_file"].read_text(encoding="utf-8")
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )
    backups = list(openacp_env["backup_dir"].glob("settings-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original


def test_backup_retention_prunes(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(get_settings(), "openacp_backup_retention", 3)
    for _ in range(6):
        client.patch(
            "/api/openacp/channel-bindings",
            json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
            headers=auth,
        )
    assert len(list(openacp_env["backup_dir"].glob("settings-*.json"))) == 3


def test_delete_all_bindings_writes_empty_object(client, auth, openacp_env):
    client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])]},
        headers=auth,
    )
    response = client.patch("/api/openacp/channel-bindings", json={"bindings": []}, headers=auth)
    assert response.status_code == 200

    on_disk = read_file(openacp_env["settings_file"])
    assert on_disk["channelBindings"] == {}
    assert on_disk["botToken"] == BOT_TOKEN


def test_revision_mismatch_returns_409(client, auth, openacp_env):
    stale = get_revision(client)

    # Something else writes the file in the meantime.
    data = read_file(openacp_env["settings_file"])
    data["guildId"] = "999999999999999999"
    openacp_env["settings_file"].write_text(json.dumps(data, indent=2) + "\n\n", encoding="utf-8")

    response = client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["workspace_a"])], "revision": stale},
        headers=auth,
    )
    assert response.status_code == 409
    assert "channelBindings" not in read_file(openacp_env["settings_file"])


# --- validation ------------------------------------------------------------


@pytest.mark.parametrize(
    "channel_id, agent, use_real_workspace",
    [
        ("123", "claude", True),          # too short to be a snowflake
        ("not-a-snowflake", "claude", True),
        (CHANNEL_A, "", True),            # empty agent
        (CHANNEL_A, "claude", False),     # empty workspace
    ],
)
def test_invalid_rows_rejected(client, auth, openacp_env, channel_id, agent, use_real_workspace):
    workspace = openacp_env["workspace_a"] if use_real_workspace else ""
    response = client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [{"channel_id": channel_id, "agent": agent, "workspace": workspace}]},
        headers=auth,
    )
    assert response.status_code == 422


def test_nonexistent_workspace_rejected_and_file_untouched(client, auth, openacp_env):
    before = openacp_env["settings_file"].read_text(encoding="utf-8")
    response = client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, openacp_env["missing"])]},
        headers=auth,
    )
    assert response.status_code == 422
    assert openacp_env["settings_file"].read_text(encoding="utf-8") == before


def test_unc_workspace_rejected(client, auth, openacp_env):
    response = client.patch(
        "/api/openacp/channel-bindings",
        json={"bindings": [binding(CHANNEL_A, "\\\\server\\share")]},
        headers=auth,
    )
    assert response.status_code == 422


def test_duplicate_channel_id_rejected(client, auth, openacp_env):
    response = client.patch(
        "/api/openacp/channel-bindings",
        json={
            "bindings": [
                binding(CHANNEL_A, openacp_env["workspace_a"]),
                binding(CHANNEL_A, openacp_env["workspace_b"]),
            ]
        },
        headers=auth,
    )
    assert response.status_code == 422


# --- agents ----------------------------------------------------------------


def test_get_agents(client, openacp_env):
    body = client.get("/api/openacp/agents").json()
    assert body == [
        {"id": "claude", "name": "Claude Agent"},
        {"id": "codex", "name": "Codex"},
    ]


def test_get_agents_missing_file(client, openacp_env):
    openacp_env["agents_file"].unlink()
    assert client.get("/api/openacp/agents").json() == []


def test_get_agent_catalog(client, openacp_env):
    body = client.get("/api/openacp/agents/catalog").json()
    ids = {entry["id"] for entry in body}
    assert ids == set(openacp_daemon.AGENT_CATALOG)


def test_install_agent(client, auth, openacp_env, fake_daemon):
    calls = fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),  # workspace lookup
        FakeCompleted(0, stdout='{"success":true}'),
    )
    response = client.post("/api/openacp/agents/gemini/install", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["agent_id"] == "gemini"
    assert calls[1]["argv"][1:] == ["agents", "install", "gemini", "--json"]
    # Driven from the workspace, same as every other openacp command here.
    assert calls[1]["kwargs"]["cwd"] == "C:\\ws"


def test_install_agent_reports_failure(client, auth, openacp_env, fake_daemon):
    fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),
        FakeCompleted(1, stderr="network error"),
    )
    body = client.post("/api/openacp/agents/kimi/install", headers=auth).json()

    assert body["ok"] is False
    assert "network error" in body["output"]


def test_install_agent_detects_failure_despite_exit_code_0(client, auth, openacp_env, fake_daemon):
    """Mirrors cancel_session: the CLI can exit 0 while its own --json body
    reports the failure (success:false, or success:true with a data.error)."""
    fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),
        FakeCompleted(0, stdout='{"success":false,"error":{"message":"network error"}}'),
    )
    body = client.post("/api/openacp/agents/kimi/install", headers=auth).json()
    assert body["ok"] is False


def test_install_agent_retries_with_force_when_already_installed(
    client, auth, openacp_env, fake_daemon
):
    """openacp can think an agent is already installed (some global/npm-level
    check) while this workspace's own agents.json was never written — e.g. a
    workspace restored from another PC's settings bundle. --force should make
    the CLI (re)write the workspace record instead of leaving it missing."""
    calls = fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),  # workspace lookup
        FakeCompleted(
            1,
            stdout=(
                '{"success":false,"error":{"code":"INSTALL_FAILED",'
                '"message":"Claude Agent is already installed (v0.63.0). '
                'Use --force to reinstall."}}'
            ),
        ),
        FakeCompleted(0, stdout='{"success":true}'),  # --force retry
    )
    response = client.post("/api/openacp/agents/claude/install", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert calls[2]["argv"][1:] == ["agents", "install", "claude", "--force", "--json"]


def test_install_agent_does_not_force_retry_other_failures(client, auth, openacp_env, fake_daemon):
    """Only the specific "already installed, use --force" failure is retried —
    a genuine failure (network error, bad package, ...) should not be masked
    by silently reinstalling with --force."""
    calls = fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),
        FakeCompleted(1, stderr="network error"),
    )
    body = client.post("/api/openacp/agents/claude/install", headers=auth).json()

    assert body["ok"] is False
    assert len(calls) == 2


def test_install_agent_serializes_against_other_actions(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: "C:\\fake\\openacp.CMD")
    # Simulate a restart/stop/install already in flight, holding the shared lock.
    openacp_daemon._action_lock.acquire()
    try:
        response = client.post("/api/openacp/agents/claude/install", headers=auth)
        assert response.status_code == 409
    finally:
        openacp_daemon._action_lock.release()


def test_install_agent_rejects_unknown_id(client, auth, openacp_env, fake_daemon):
    calls = fake_daemon(FakeCompleted(0, stdout=ONLINE_STATUS))
    response = client.post("/api/openacp/agents/not-a-real-agent/install", headers=auth)

    assert response.status_code == 422
    assert calls == []


def test_install_agent_without_cli_returns_503(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: None)
    assert client.post("/api/openacp/agents/claude/install", headers=auth).status_code == 503


def test_install_agent_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/agents/claude/install").status_code == 401


# --- hook ------------------------------------------------------------------


class FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture
def fake_run(monkeypatch):
    """Never invoke the real script — it writes into %APPDATA%."""
    calls: list[dict] = []

    def factory(result):
        def runner(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            if isinstance(result, Exception):
                raise result
            return result

        monkeypatch.setattr(openacp_hook.subprocess, "run", runner)
        return calls

    return factory


def test_hook_status_installed(client, openacp_env, fake_run):
    fake_run(FakeCompleted(0))
    body = client.get("/api/openacp/hook-status").json()
    assert body["installed"] is True


def test_hook_status_not_installed_uses_exit_code_2(client, openacp_env, fake_run):
    fake_run(FakeCompleted(2))
    body = client.get("/api/openacp/hook-status").json()
    assert body["installed"] is False


def test_hook_status_unknown_on_script_error(client, openacp_env, fake_run):
    fake_run(FakeCompleted(1, stderr="ERROR: adapter dist not found"))
    body = client.get("/api/openacp/hook-status").json()
    assert body["installed"] is None
    assert "adapter dist not found" in body["detail"]


def test_hook_status_handles_missing_node(client, openacp_env, fake_run):
    fake_run(FileNotFoundError())
    body = client.get("/api/openacp/hook-status").json()
    assert body["installed"] is None
    assert "node" in body["detail"].lower()


def test_hook_status_handles_timeout(client, openacp_env, fake_run):
    fake_run(subprocess.TimeoutExpired(cmd="node", timeout=1))
    body = client.get("/api/openacp/hook-status").json()
    assert body["installed"] is None
    assert "timed out" in body["detail"]


def test_redeploy_succeeds(client, auth, openacp_env, fake_run):
    fake_run(FakeCompleted(0, stdout="Patched adapter.js"))
    response = client.post("/api/openacp/redeploy", headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["restart_required"] is True
    assert "Patched adapter.js" in body["output"]


def test_redeploy_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/redeploy").status_code == 401


def test_redeploy_passes_no_user_input(client, auth, openacp_env, fake_run):
    calls = fake_run(FakeCompleted(0))
    client.post("/api/openacp/redeploy", headers=auth)

    assert len(calls) == 1
    argv = calls[0]["argv"]
    assert len(argv) == 2
    assert argv[1].endswith("install-hook.mjs")
    assert calls[0]["kwargs"]["shell"] is False


def test_redeploy_requires_built_module(client, auth, openacp_env):
    (openacp_env["module_dir"] / "dist" / "index.js").unlink()
    response = client.post("/api/openacp/redeploy", headers=auth)
    assert response.status_code == 422
    assert "npm run build" in response.json()["detail"]


# --- daemon ----------------------------------------------------------------

ONLINE_STATUS = json.dumps(
    {
        "success": True,
        "data": {
            "status": "online",
            "pid": 4242,
            "dir": "C:\\ws\\.openacp",
            "mode": "foreground",
            "channels": ["discord"],
        },
    }
)

OFFLINE_STATUS = json.dumps(
    {"success": True, "data": {"status": "offline", "pid": None, "dir": "C:\\ws\\.openacp"}}
)

# What "openacp api status --json" returns from a foreground instance.
FOREGROUND_SESSIONS = json.dumps(
    {
        "success": True,
        "data": {
            "sessions": [
                {"id": "aaa", "status": "active"},
                {"id": "bbb", "status": "finished"},
            ]
        },
    }
)


@pytest.fixture
def fake_daemon(monkeypatch):
    """Never touch the real daemon."""
    calls: list[dict] = []

    def factory(*results):
        queue = list(results)

        def runner(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            outcome = queue.pop(0) if len(queue) > 1 else queue[0]
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: "C:\\fake\\openacp.CMD")
        monkeypatch.setattr(openacp_daemon.subprocess, "run", runner)
        return calls

    return factory


@pytest.fixture
def fake_spawn(monkeypatch):
    """Never actually open a console window."""
    spawned: list[dict] = []

    def factory():
        def popen(argv, **kwargs):
            spawned.append({"argv": argv, "kwargs": kwargs})
            return None

        monkeypatch.setattr(openacp_daemon.subprocess, "Popen", popen)
        return spawned

    return factory


@pytest.fixture
def no_sleep(monkeypatch):
    """Keeps restart tests instant — the startup poll would otherwise spin for
    STARTUP_TIMEOUT_SECONDS of real time whenever OpenACP stays offline."""
    monkeypatch.setattr(openacp_daemon.time, "sleep", lambda _: None)
    monkeypatch.setattr(openacp_daemon, "STARTUP_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(openacp_daemon, "STOP_SETTLE_SECONDS", 0)


def test_daemon_status_online_counts_active_sessions(client, openacp_env, fake_daemon):
    fake_daemon(FakeCompleted(0, stdout=ONLINE_STATUS))
    body = client.get("/api/openacp/daemon-status").json()

    assert body["running"] is True
    assert body["status"] == "online"
    assert body["pid"] == 4242
    assert body["channels"] == ["discord"]
    # active + initializing, not finished
    assert body["active_sessions"] == 2


def test_daemon_status_offline_reports_no_sessions(client, openacp_env, fake_daemon):
    fake_daemon(FakeCompleted(0, stdout=OFFLINE_STATUS))
    body = client.get("/api/openacp/daemon-status").json()

    assert body["running"] is False
    assert body["status"] == "offline"
    assert body["active_sessions"] == 0


def test_daemon_status_detects_foreground_instance(client, openacp_env, fake_daemon):
    """A foreground instance writes no PID file, so "openacp status" calls it
    offline. It has to be found through the daemon API instead."""
    fake_daemon(
        FakeCompleted(0, stdout=OFFLINE_STATUS),
        FakeCompleted(0, stdout=FOREGROUND_SESSIONS),
    )
    body = client.get("/api/openacp/daemon-status").json()

    assert body["running"] is True
    assert body["foreground"] is True
    assert body["mode"] == "foreground"
    assert body["pid"] is None
    # Live sessions from the API, not the on-disk file: only "active" counts.
    assert body["active_sessions"] == 1


def test_foreground_restart_runs_the_restart_script(
    client, auth, openacp_env, fake_daemon, fake_spawn, no_sleep
):
    """A foreground instance writes no PID file, so "openacp stop" cannot see it
    and the CLI alone would spawn a second instance fighting the first one for
    the API port. restart-openacp.ps1 kills the node process and reopens the
    window instead."""
    calls = fake_daemon(
        FakeCompleted(0, stdout=OFFLINE_STATUS),        # status: no daemon
        FakeCompleted(0, stdout=FOREGROUND_SESSIONS),   # api status: alive after all
        FakeCompleted(0, stdout="OpenACP stopped"),     # the PowerShell script
        FakeCompleted(0, stdout=OFFLINE_STATUS),        # status again, after
        FakeCompleted(0, stdout=FOREGROUND_SESSIONS),   # api status: back up
    )
    spawned = fake_spawn()
    response = client.post("/api/openacp/daemon/restart", headers=auth)
    body = response.json()

    assert response.status_code == 200
    assert body["ok"] is True
    assert body["status"]["foreground"] is True

    script_argv = calls[2]["argv"]
    assert script_argv[-3:] == [
        "-File",
        str(openacp_env["scripts_dir"] / "restart-openacp.ps1"),
        # The dashboard already confirmed; the script must not wait on a prompt
        # nobody can answer.
        "-Force",
    ]
    assert calls[2]["kwargs"]["shell"] is False
    # The window is opened by the script, not by a Popen from the request.
    assert spawned == []


def test_foreground_stop_runs_the_stop_script(
    client, auth, openacp_env, fake_daemon, fake_spawn, no_sleep
):
    calls = fake_daemon(
        FakeCompleted(0, stdout=OFFLINE_STATUS),
        FakeCompleted(0, stdout=FOREGROUND_SESSIONS),
        FakeCompleted(0, stdout="OpenACP stopped"),      # the PowerShell script
        FakeCompleted(0, stdout=OFFLINE_STATUS),         # status: gone
        FakeCompleted(0, stdout='{"success": false}'),   # api status: nothing answers
    )
    fake_spawn()
    body = client.post("/api/openacp/daemon/stop", headers=auth).json()

    assert body["ok"] is True
    assert body["status"]["running"] is False
    assert calls[2]["argv"][-2:] == [
        "-File",
        str(openacp_env["scripts_dir"] / "stop-openacp.ps1"),
    ]


def test_foreground_action_without_its_script_is_reported(
    client, auth, openacp_env, fake_daemon, fake_spawn, no_sleep
):
    """A checkout missing scripts\\ must say so rather than look like a dead daemon."""
    (openacp_env["scripts_dir"] / "restart-openacp.ps1").unlink()
    fake_daemon(
        FakeCompleted(0, stdout=OFFLINE_STATUS),
        FakeCompleted(0, stdout=FOREGROUND_SESSIONS),
    )
    fake_spawn()
    response = client.post("/api/openacp/daemon/restart", headers=auth)

    assert response.status_code == 503
    assert "restart-openacp.ps1" in response.json()["detail"]


def test_sessions_are_listed_and_paired_with_projects(client, auth, openacp_env, fake_daemon):
    client.post(
        "/api/projects",
        json={"name": "TheLosers", "repository_path": openacp_env["workspace_a"]},
        headers=auth,
    )
    fake_daemon(
        FakeCompleted(
            0,
            stdout=json.dumps(
                {
                    "success": True,
                    "data": {
                        "sessions": [
                            {
                                "id": "old",
                                "agent": "codex",
                                "status": "finished",
                                "name": "earlier thread",
                                "workspace": openacp_env["workspace_a"],
                                "lastActiveAt": "2026-07-19T10:00:00.000Z",
                            },
                            {
                                "id": "new",
                                "agent": "codex",
                                "status": "active",
                                "name": "halo",
                                "workspace": openacp_env["workspace_a"],
                                "lastActiveAt": "2026-07-19T19:00:00.000Z",
                                "promptRunning": True,
                                "queueDepth": 2,
                                "dangerousMode": True,
                            },
                            {
                                "id": "elsewhere",
                                "agent": "claude",
                                "status": "active",
                                "workspace": "C:\\somewhere\\else",
                                "lastActiveAt": "2026-07-19T12:00:00.000Z",
                            },
                        ]
                    },
                }
            ),
        )
    )

    body = client.get("/api/openacp/sessions").json()

    # Newest activity first, so the dashboard shows current work at the top.
    assert [s["id"] for s in body] == ["new", "elsewhere", "old"]
    assert body[0]["project_name"] == "TheLosers"
    assert body[0]["prompt_running"] is True
    assert body[0]["queue_depth"] == 2
    assert body[0]["dangerous_mode"] is True
    # A workspace outside every project stays unlinked rather than being hidden.
    assert body[1]["project_name"] is None
    # "active" is computed here so the dashboard need not repeat the status list.
    assert [s["active"] for s in body] == [True, True, False]


def test_sessions_empty_when_openacp_is_down(client, openacp_env, fake_daemon):
    fake_daemon(FakeCompleted(1, stderr="connection refused"))
    assert client.get("/api/openacp/sessions").json() == []


def test_daemon_status_missing_cli_is_not_an_error(client, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: None)
    body = client.get("/api/openacp/daemon-status").json()

    assert body["status"] == "unknown"
    assert body["running"] is False
    assert "PATH" in body["detail"]


def test_daemon_status_handles_timeout(client, openacp_env, fake_daemon):
    fake_daemon(subprocess.TimeoutExpired(cmd="openacp", timeout=1))
    body = client.get("/api/openacp/daemon-status").json()
    assert body["status"] == "unknown"
    assert "timed out" in body["detail"]


def test_daemon_restart(client, auth, openacp_env, fake_daemon, fake_spawn, no_sleep):
    calls = fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),   # foreground check
        FakeCompleted(0, stdout=ONLINE_STATUS),   # workspace lookup
        FakeCompleted(0, stdout="OpenACP stopped"),
        FakeCompleted(0, stdout=ONLINE_STATUS),   # status afterwards
    )
    spawned = fake_spawn()
    response = client.post("/api/openacp/daemon/restart", headers=auth)

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["action"] == "restart"
    assert body["status"]["running"] is True

    # Restart is stop + a fresh process, never "openacp restart": that one runs
    # inside the calling shell and would block the request.
    assert calls[2]["argv"][1:] == ["stop"]
    assert len(spawned) == 1
    # "start" would daemonize regardless of runMode — the window would just
    # print a PID and close.
    assert spawned[0]["argv"][1:] == ["--foreground"]
    # OpenACP is driven from its workspace, not from the backend's cwd.
    assert spawned[0]["kwargs"]["cwd"] == "C:\\ws"
    assert spawned[0]["kwargs"]["shell"] is False
    # Its own visible console — otherwise it would have nowhere to log and
    # would die with the backend process.
    assert spawned[0]["kwargs"]["creationflags"] == openacp_daemon.CREATE_NEW_CONSOLE


def test_daemon_restart_reports_failure_to_come_up(
    client, auth, openacp_env, fake_daemon, fake_spawn, no_sleep
):
    fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),   # foreground check
        FakeCompleted(0, stdout=ONLINE_STATUS),   # workspace lookup
        FakeCompleted(0, stdout="OpenACP stopped"),
        FakeCompleted(0, stdout=OFFLINE_STATUS),  # never comes back
    )
    fake_spawn()
    body = client.post("/api/openacp/daemon/restart", headers=auth).json()

    assert body["ok"] is False
    assert "did not come up" in body["output"]


def test_daemon_restart_without_cli_does_not_spawn(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: None)
    spawned: list = []
    monkeypatch.setattr(
        openacp_daemon.subprocess, "Popen", lambda *a, **k: spawned.append(a) or None
    )

    assert client.post("/api/openacp/daemon/restart", headers=auth).status_code == 503
    assert spawned == []


def test_daemon_stop(client, auth, openacp_env, fake_daemon):
    calls = fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),   # foreground check
        FakeCompleted(0, stdout=ONLINE_STATUS),   # workspace lookup
        FakeCompleted(0, stdout="OpenACP daemon stopped"),
        FakeCompleted(0, stdout=OFFLINE_STATUS),
    )
    body = client.post("/api/openacp/daemon/stop", headers=auth).json()

    assert body["ok"] is True
    assert body["action"] == "stop"
    assert body["status"]["running"] is False
    assert calls[2]["argv"][1] == "stop"


def test_daemon_restart_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/daemon/restart").status_code == 401


def test_daemon_stop_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/daemon/stop").status_code == 401


def test_daemon_action_reports_failure(client, auth, openacp_env, fake_daemon):
    fake_daemon(
        FakeCompleted(0, stdout=ONLINE_STATUS),   # foreground check
        FakeCompleted(0, stdout=ONLINE_STATUS),   # workspace lookup
        FakeCompleted(1, stderr="daemon refused to stop"),
        FakeCompleted(0, stdout=ONLINE_STATUS),
    )
    body = client.post("/api/openacp/daemon/stop", headers=auth).json()

    assert body["ok"] is False
    assert "refused to stop" in body["output"]


def test_daemon_action_without_cli_returns_503(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: None)
    response = client.post("/api/openacp/daemon/restart", headers=auth)
    assert response.status_code == 503


# --- Session cancel ---------------------------------------------------------


def test_cancel_session(client, auth, openacp_env, fake_daemon):
    calls = fake_daemon(
        FakeCompleted(0, stdout='{"success": true, "data": {"cancelled": true, "sessionId": "abc-123"}}')
    )
    body = client.post("/api/openacp/sessions/abc-123/cancel", headers=auth).json()

    assert body["ok"] is True
    assert body["session_id"] == "abc-123"
    assert calls[0]["argv"][1:] == ["api", "cancel", "abc-123", "--json"]


def test_cancel_session_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/sessions/abc-123/cancel").status_code == 401


def test_cancel_session_rejects_invalid_id(client, auth, openacp_env, fake_daemon):
    fake_daemon(FakeCompleted(0, stdout='{"success": true, "data": {}}'))
    response = client.post("/api/openacp/sessions/abc%20123;rm/cancel", headers=auth)
    assert response.status_code == 422


def test_cancel_session_reports_cli_failure(client, auth, openacp_env, fake_daemon):
    fake_daemon(
        FakeCompleted(
            0, stdout='{"success": false, "error": {"code": "NOT_FOUND", "message": "no such session"}}'
        )
    )
    response = client.post("/api/openacp/sessions/abc-123/cancel", headers=auth)

    assert response.status_code == 502
    assert "no such session" in response.json()["detail"]


def test_cancel_session_reports_data_error(client, auth, openacp_env, fake_daemon):
    """Some failures come back success:true with an error inside data."""
    fake_daemon(
        FakeCompleted(0, stdout='{"success": true, "data": {"error": "Session not available"}}')
    )
    response = client.post("/api/openacp/sessions/abc-123/cancel", headers=auth)

    assert response.status_code == 502
    assert "Session not available" in response.json()["detail"]


def test_cancel_session_without_cli_returns_503(client, auth, openacp_env, monkeypatch):
    monkeypatch.setattr(openacp_daemon.shutil, "which", lambda _: None)
    response = client.post("/api/openacp/sessions/abc-123/cancel", headers=auth)
    assert response.status_code == 503


# --- Settings transfer ------------------------------------------------------


@pytest.fixture
def bundle_path(tmp_path, monkeypatch):
    """A repo bundle location, wired into settings. Same tmp_path the openacp_env
    fixture uses, so the live settings_file and this bundle sit side by side."""
    path = tmp_path / "openacp-config" / "settings.json"
    monkeypatch.setattr(get_settings(), "openacp_settings_export_path", str(path))
    return path


def test_transfer_status_before_export(client, openacp_env, bundle_path):
    body = client.get("/api/openacp/settings/transfer-status").json()
    assert body["live_exists"] is True
    assert body["bundle_exists"] is False
    assert body["bundle_has_token"] is None
    # The live file has a token; the status endpoint must never echo it.
    assert BOT_TOKEN not in body.get("bundle_path", "")


def test_export_copies_live_into_bundle(client, auth, openacp_env, bundle_path):
    body = client.post("/api/openacp/settings/export", headers=auth).json()

    assert body["ok"] is True
    assert body["action"] == "export"
    assert body["has_token"] is True
    assert bundle_path.is_file()
    # The bundle is a faithful copy, token included.
    assert read_file(bundle_path)["botToken"] == BOT_TOKEN


def test_export_response_never_contains_token(client, auth, openacp_env, bundle_path):
    response = client.post("/api/openacp/settings/export", headers=auth)
    assert BOT_TOKEN not in response.text


def test_export_requires_write_token(client, openacp_env, bundle_path):
    assert client.post("/api/openacp/settings/export").status_code == 401


def test_export_without_live_settings_returns_422(client, auth, openacp_env, bundle_path):
    openacp_env["settings_file"].unlink()
    assert client.post("/api/openacp/settings/export", headers=auth).status_code == 422


def test_import_applies_bundle_and_backs_up_live(client, auth, openacp_env, bundle_path):
    # Prepare a bundle that differs from the live file.
    bundle_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_data = dict(BASE_SETTINGS)
    bundle_data["guildId"] = "changed-on-other-pc"
    bundle_path.write_text(json.dumps(bundle_data), encoding="utf-8")

    body = client.post("/api/openacp/settings/import", headers=auth).json()

    assert body["ok"] is True
    assert body["action"] == "import"
    # Live now matches the bundle …
    assert read_file(openacp_env["settings_file"])["guildId"] == "changed-on-other-pc"
    # … and the old live file was preserved.
    backup = openacp_env["settings_file"].with_suffix(".json.pre-import.bak")
    assert backup.is_file()
    assert read_file(backup)["guildId"] == BASE_SETTINGS["guildId"]


def test_import_requires_write_token(client, openacp_env, bundle_path):
    assert client.post("/api/openacp/settings/import").status_code == 401


def test_import_without_bundle_returns_422(client, auth, openacp_env, bundle_path):
    assert client.post("/api/openacp/settings/import", headers=auth).status_code == 422


# --- Installation -----------------------------------------------------------


def _which_factory(npm=None, openacp=None):
    """which() stub returning a path per tool name, or None when absent."""
    mapping = {"npm": npm, "openacp": openacp}

    def which(name):
        return mapping.get(name)

    return which


@pytest.fixture
def fake_install(monkeypatch):
    """Never run the real npm/openacp binaries."""
    calls: list[dict] = []

    def factory(which, *results):
        queue = list(results)

        def runner(argv, **kwargs):
            calls.append({"argv": argv, "kwargs": kwargs})
            outcome = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else FakeCompleted(0))
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        monkeypatch.setattr(openacp_install.shutil, "which", which)
        monkeypatch.setattr(openacp_install.subprocess, "run", runner)
        return calls

    return factory


def test_install_status_when_installed(client, openacp_env, fake_install):
    fake_install(
        _which_factory(npm="C:\\npm.CMD", openacp="C:\\openacp.CMD"),
        FakeCompleted(0, stdout="openacp v2026.518.2"),   # --version
        FakeCompleted(0, stdout="@openacp/discord-adapter@1.0.0"),  # npm ls adapter
    )
    body = client.get("/api/openacp/install-status").json()

    assert body["cli_installed"] is True
    assert body["cli_version"] == "2026.518.2"
    assert body["adapter_installed"] is True
    assert body["npm_available"] is True


def test_install_status_when_cli_missing(client, openacp_env, fake_install):
    fake_install(
        _which_factory(npm="C:\\npm.CMD", openacp=None),
        FakeCompleted(1),  # npm ls adapter — not present
    )
    body = client.get("/api/openacp/install-status").json()

    assert body["cli_installed"] is False
    assert body["cli_version"] is None
    assert body["adapter_installed"] is False
    assert "not installed" in body["detail"].lower()


def test_install_status_when_npm_missing(client, openacp_env, fake_install):
    fake_install(_which_factory(npm=None, openacp=None))
    body = client.get("/api/openacp/install-status").json()

    assert body["npm_available"] is False
    assert body["adapter_installed"] is None
    assert "npm" in body["detail"].lower()


def test_install_runs_global_npm_with_both_packages(client, auth, openacp_env, fake_install):
    calls = fake_install(
        _which_factory(npm="C:\\npm.CMD", openacp="C:\\openacp.CMD"),
        FakeCompleted(0, stdout="added 1 package"),   # npm install
        FakeCompleted(0, stdout="openacp v2026.518.2"),  # --version in read_status
        FakeCompleted(0, stdout="@openacp/discord-adapter@1.0.0"),  # npm ls
    )
    body = client.post("/api/openacp/install", headers=auth).json()

    assert body["ok"] is True
    assert body["status"]["cli_installed"] is True
    # Fixed argv, both packages, global, shell=False — no user input reaches it.
    # The versions are pinned: install-hook.mjs patches the adapter's compiled
    # output by matching exact anchors, so "latest" could silently break it.
    install_argv = calls[0]["argv"]
    assert install_argv[1:] == [
        "install",
        "-g",
        f"@openacp/cli@{openacp_install.CLI_VERSION}",
        f"@openacp/discord-adapter@{openacp_install.ADAPTER_VERSION}",
    ]
    assert calls[0]["kwargs"]["shell"] is False


def test_install_requires_write_token(client, openacp_env):
    assert client.post("/api/openacp/install").status_code == 401


def test_install_without_npm_returns_422(client, auth, openacp_env, fake_install):
    fake_install(_which_factory(npm=None, openacp=None))
    response = client.post("/api/openacp/install", headers=auth)

    assert response.status_code == 422
    assert "npm" in response.json()["detail"].lower()


def test_install_reports_npm_failure(client, auth, openacp_env, fake_install):
    fake_install(
        _which_factory(npm="C:\\npm.CMD", openacp=None),
        FakeCompleted(1, stderr="npm ERR! network timeout"),  # npm install fails
        FakeCompleted(1),  # npm ls in read_status — still missing
    )
    body = client.post("/api/openacp/install", headers=auth).json()

    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert "network timeout" in body["output"]


def test_install_handles_timeout(client, auth, openacp_env, fake_install):
    fake_install(
        _which_factory(npm="C:\\npm.CMD", openacp=None),
        subprocess.TimeoutExpired(cmd="npm", timeout=1),
    )
    response = client.post("/api/openacp/install", headers=auth)

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]
