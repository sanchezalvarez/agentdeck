# Agent Hub — working reference

Operational detail for anyone (human or agent) working *on* this repository. For what Agent Hub
is and how to get it running, see [README.md](README.md).

**Division of responsibilities (V1):**

- **OpenACP** owns Discord communication and agent sessions.
- **Agent Hub records and displays work**, and acts as a **control panel for OpenACP**: it edits
  the Discord adapter's channel-binding configuration, re-applies the adapter hook, and can
  restart or stop the OpenACP daemon.
- **Agent Hub never starts or stops Claude Code or Codex directly** — agents are launched by
  OpenACP in response to Discord messages. It also cannot restart its own backend or dashboard;
  use `stop-agent-hub.bat` / `start-agent-hub.bat` for that.

Task IDs are sequential: `REM-001`, `REM-002`, … Agents finish successful work as
`needs_review`; only a human approval in the dashboard moves a task to `completed`.

## Components

- **backend/** — FastAPI + SQLModel + SQLite + Alembic. Stores projects, tasks, lifecycle
  events, artifacts and worker heartbeats. All endpoints live under `/api`.
- **cli/** — `agent-report`, a Windows-friendly Python CLI that talks only to the HTTP API
  (never directly to SQLite).
- **frontend/** — Next.js (App Router, TypeScript strict, Tailwind, shadcn-style components).
  Live updates via SSE with polling fallback.
- **templates/** — reporting instructions to copy into project-level `CLAUDE.md` / `AGENTS.md`.
- **scripts/** — PowerShell setup and start scripts.
- **openacp-channel-bindings/** — Discord channel → project bindings for the OpenACP adapter
  (TypeScript + vitest).

## Manual setup

```powershell
.\scripts\setup.ps1
```

Verifies Python/Node, creates `backend\.venv`, installs backend + CLI + frontend dependencies,
builds `openacp-channel-bindings`, and copies `.env.example` to `.env` (an existing `.env` is
never overwritten).

A `.venv` copied from another PC hard-codes that PC's Python home and cannot start here;
`setup.ps1` detects this and rebuilds it.

## Environment variables

Configured in `.env` at the repository root (see `.env.example`):

| Variable | Default | Purpose |
| --- | --- | --- |
| `AGENT_HUB_HOST` | `127.0.0.1` | Backend bind address — keep localhost |
| `AGENT_HUB_PORT` | `8765` | Backend port |
| `AGENT_HUB_DATABASE_URL` | `sqlite:///./agent_hub.db` | SQLite URL (relative to `backend/`) |
| `AGENT_HUB_WRITE_TOKEN` | *(empty)* | Bearer token required for **all write endpoints**. Empty = open writes (local dev only). Generate: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `AGENT_HUB_CORS_ORIGINS` | `http://localhost:3000` | Allowed dashboard origins (comma-separated) |
| `AGENT_HUB_WORKER_STALE_SECONDS` | `300` (`1200` in `.env`) | A worker with no heartbeat for this long is shown as offline — keep it above the heartbeat task's interval |
| `AGENT_HUB_DISCORD_SUMMARY_WEBHOOK` | *(empty)* | Discord channel webhook receiving task summaries — see [Discord summaries](#discord-summaries). Empty disables them |
| `AGENT_HUB_URL` | `http://127.0.0.1:8765` | Used by the `agent-report` CLI |

Read-only endpoints (GET) are accessible locally without authentication in V1.
If you set a write token and want to use dashboard actions (approve/reject/archive, project
editing), also set `NEXT_PUBLIC_AGENT_HUB_WRITE_TOKEN` in `frontend\.env.local` — note this
exposes the token to the local browser, which is acceptable only for this local-only setup.

OpenACP-related settings (all optional): `AGENT_HUB_OPENACP_SETTINGS_PATH`,
`AGENT_HUB_OPENACP_AGENTS_PATH`, `AGENT_HUB_OPENACP_BINDINGS_MODULE_DIR`,
`AGENT_HUB_OPENACP_SETTINGS_BACKUP_DIR`, `AGENT_HUB_OPENACP_BACKUP_RETENTION`,
`AGENT_HUB_OPENACP_HOOK_TIMEOUT_SECONDS`, `AGENT_HUB_OPENACP_INSTALL_TIMEOUT_SECONDS`,
`AGENT_HUB_OPENACP_SETTINGS_EXPORT_PATH` (default `openacp-config/settings.json`).

Screenshot settings: `AGENT_HUB_SCREENSHOT_DIR` (default `./screenshots`),
`AGENT_HUB_SCREENSHOT_INSTALL_TIMEOUT_SECONDS`.

## Database migrations

Alembic manages the schema (the app does not rely on `create_all`):

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
alembic upgrade head                      # apply migrations
alembic revision --autogenerate -m "..."  # create a new migration after model changes
alembic downgrade -1                      # roll back one migration
```

`scripts\start-backend.ps1` runs `alembic upgrade head` automatically before starting.

## Scripts

```powershell
.\scripts\start-backend.ps1    # migrations + FastAPI on http://127.0.0.1:8765
.\scripts\start-frontend.ps1   # Next.js on http://localhost:3000
.\scripts\start-all.ps1        # backend + dashboard + OpenACP, one window each
.\scripts\stop-all.ps1         # stop all three (-KeepOpenAcp leaves OpenACP running)
.\scripts\start-openacp.ps1    # OpenACP alone, in this window
.\scripts\restart-openacp.ps1  # restart OpenACP from the terminal
.\scripts\cleanup-openacp-tunnels.ps1  # kill leaked cloudflared tunnels (-All: every OpenACP tunnel)
.\scripts\make-distributable.ps1       # clean shareable zip (see below)
```

`start-agent-hub.bat` useful flags: `-DryRun` reports what it would start without starting
anything, `-NoBrowser` skips opening the dashboard.

`stop-agent-hub.bat` exists because closing the console windows does not reliably terminate the
processes they started. It only touches processes whose command line points at this repository
or at the OpenACP CLI.

Health check: <http://127.0.0.1:8765/api/health> • Dashboard: <http://localhost:3000>

## Worker heartbeat task

The **AgentHub Heartbeat** scheduled task posts a worker heartbeat every 15 minutes. Keep
`AGENT_HUB_WORKER_STALE_SECONDS` (1200 in `.env.example`) above that interval — with the 300s
default the worker would report offline between two beats. It runs
`scripts\heartbeat-silent.vbs`, which starts `scripts\heartbeat.ps1` with no console window —
pointing the task straight at `powershell.exe` flashes a window on screen every time it fires,
because Task Scheduler creates the console before `-WindowStyle Hidden` can take effect.

The alternative is to set the task to *Run whether the user is logged on or not*, which needs
administrator rights:

```powershell
$p = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Limited
Set-ScheduledTask -TaskName 'AgentHub Heartbeat' -Principal $p
```

## Running OpenACP

OpenACP runs in the **foreground**, in a console window of its own, so its log is visible while
it works. Closing that window stops OpenACP and every agent session under it.

The command is `openacp --foreground`, not `openacp start`: the `start` subcommand always
daemonizes, whatever `runMode` says in the config. A restart is therefore stop + a freshly
spawned window rather than `openacp restart`, which would otherwise run inside the calling shell
and die with it.

`restart-openacp.ps1` asks for confirmation first, because restarting terminates running agent
sessions; pass `-Force` to skip the prompt.

The OpenACP CLI does not stop its cloudflared tunnel child when it is killed or restarted, so
orphaned tunnels used to accumulate (one per restart, each ~30 MB RAM plus network traffic).
The start, stop and restart scripts now run `cleanup-openacp-tunnels.ps1` automatically; run it
by hand if tunnels pile up anyway (`Get-Process cloudflared` shows more than one).

Starting OpenACP from a launcher script is a desktop convenience and does **not** change the
rule above: the Agent Hub backend itself never starts or stops OpenACP.

## CLI installation

```powershell
.\scripts\install-agent-report.ps1
agent-report --help
```

The script installs the package into `backend\.venv` and copies the generated launcher into a
directory on the user PATH.

It deliberately does **not** use `pip install --user`. Agent processes run with user-site
disabled, so a `--user` install fails at import time even though the command starts:

```text
ModuleNotFoundError: No module named 'agent_report'
```

`PYTHONNOUSERSITE` drops user-site from `sys.path`; a venv's own site-packages is unaffected.
The launcher is copied as a real `.exe` rather than a `.cmd` shim because Git Bash — which
agents commonly run commands through — does not resolve `.cmd` files from PATH. The script
verifies the install with user-site disabled, the way agents actually invoke it.

Re-run it after rebuilding `backend\.venv`: the launcher points into that venv by absolute path.

Agents also need `AGENT_HUB_WRITE_TOKEN` (and `AGENT_HUB_URL` if not the default) in their
environment, otherwise every write returns 401. Set them as **user** environment variables so
spawned agents inherit them, and restart OpenACP after changing them.

## CLI examples

```powershell
# Create a task (prints the generated REM-### ID)
agent-report create `
  --title "Fix DOCX table import" `
  --description "Table borders and alignment are lost." `
  --project crowforge `
  --agent claude `
  --requested-by "Lubomir"

# Start work
agent-report start `
  --task REM-104 `
  --agent claude `
  --project crowforge `
  --branch agent/rem-104-docx `
  --working-directory "D:\AgentWorkspaces\crowforge-claude"

# Milestone
agent-report progress --task REM-104 --message "Implemented table style parsing"

# Tests / build
agent-report testing --task REM-104 --kind tests --status started
agent-report testing --task REM-104 --kind tests --status passed --message "42 tests passed"

# Finish (→ needs_review)
agent-report finish `
  --task REM-104 `
  --summary "Implemented DOCX table import fixes and added tests." `
  --branch "agent/rem-104-docx" `
  --commit "a94c2e1" `
  --tests passed --build passed --exit-code 0

# Failure / blocking
agent-report fail --task REM-104 --error "Backend tests failed." --tests failed --build not_run --exit-code 1
agent-report block --task REM-104 --reason "Missing client test document."

# Artifact
agent-report artifact --task REM-104 --type screenshot --name "Preview" --path "D:\artifacts\preview.png"

# Worker heartbeat
agent-report heartbeat --worker "Rembrosoft-Main-PC" `
  --claude-available true --codex-available true --unity-available true --unity-mcp-available false

# Task summary (add --json for raw JSON on any command)
agent-report status --task REM-104
```

Exit codes: `0` success, `1` API error, `2` invalid arguments, `3` connection error.

## Reporting instructions for agents

- **Claude Code projects:** copy `templates\CLAUDE_REPORTING.md` into the project's
  `CLAUDE.md` and replace `<PROJECT_SLUG>`, `<TEST_COMMAND>`, `<BUILD_COMMAND>`,
  `<TYPECHECK_COMMAND>`, `<DEFAULT_BRANCH>`.
- **Codex projects:** copy `templates\AGENTS_REPORTING.md` into the project's `AGENTS.md`
  the same way.

## Creating the initial projects

Via the dashboard (**Projects → New project**) or the API:

```powershell
$headers = @{ Authorization = "Bearer $env:AGENT_HUB_WRITE_TOKEN" }
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8765/api/projects -Headers $headers `
  -ContentType "application/json" `
  -Body '{"name": "CrowForge", "slug": "crowforge", "project_type": "desktop", "repository_path": "D:\\Projects\\CrowForge"}'
```

Optional sample data for dashboard development (never runs automatically; skips a non-empty DB):

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
```

## Testing

```powershell
# Backend
cd backend; .\.venv\Scripts\python.exe -m pytest

# CLI
cd cli; C:\agent-hub\backend\.venv\Scripts\python.exe -m pytest

# Frontend
cd frontend
npm run lint
npm run typecheck
npm run build

# Channel bindings
cd openacp-channel-bindings; npm run verify
```

## Discord summaries

When a task **finishes**, **fails** or is **blocked**, Agent Hub posts a short summary to one
Discord channel. The text is the agent's own report — whatever it passed to `agent-report
finish --summary`, `fail --error` or `block --reason`. Nothing rewrites it and no extra model is
involved, so the message says what the agent that did the work says, whichever agent that was.

Set it up:

1. In Discord, open the target channel → **Edit Channel → Integrations → Webhooks → New Webhook**
   and copy its URL. This is *not* the **Webhooks** page of the Discord Developer Portal — that
   one pushes Discord's own events out to another application, the opposite direction.
2. Put the URL in `.env` as `AGENT_HUB_DISCORD_SUMMARY_WEBHOOK` and restart the backend.

A webhook URL addresses exactly one channel and carries no bot identity, so Agent Hub still
stores no Discord credentials. Leaving the variable empty disables the feature.

Delivery is fire-and-forget on a daemon thread: a slow or unreachable Discord is logged and
ignored, and can never make an agent's `agent-report finish` fail. Note that a summary only
appears for work that goes through `agent-report` — a Discord thread that never created a task
has nothing to report.

## OpenACP channel bindings

The **OpenACP** page in the dashboard configures which Discord channel maps to which project.
One channel = one project with a fixed agent and workspace; every thread inside that channel
becomes its own OpenACP session, created automatically from the first message — no
`/new <agent> <workspace>` needed.

The feature itself lives in `openacp-channel-bindings/` (see its README). The dashboard page
only edits its configuration and re-applies its hook.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/openacp/channel-bindings` | Current bindings (**only** the `channelBindings` key) |
| `PATCH /api/openacp/channel-bindings` | Replace all bindings (write token) |
| `GET /api/openacp/agents` | Installed OpenACP agents, for the agent dropdown |
| `GET /api/openacp/install-status` | Whether the OpenACP CLI + Discord adapter are installed, and the CLI version |
| `POST /api/openacp/install` | Install `@openacp/cli` + `@openacp/discord-adapter` globally via npm (write token) |
| `GET /api/openacp/settings/transfer-status` | Whether a settings bundle exists in the repo folder (never returns the token) |
| `POST /api/openacp/settings/export` | Copy the live settings.json (**token included**) into the gitignored repo bundle (write token) |
| `POST /api/openacp/settings/import` | Apply the repo bundle onto this PC's workspace; old file kept as `.pre-import.bak` (write token) |
| `GET /api/openacp/hook-status` | Whether the adapter hook is currently installed |
| `POST /api/openacp/redeploy` | Re-apply the hook after an adapter update (write token) |
| `GET /api/openacp/daemon-status` | Daemon state, PID, mode and count of running sessions |
| `POST /api/openacp/daemon/restart` | Restart OpenACP (write token) |
| `POST /api/openacp/daemon/stop` | Stop OpenACP (write token) |

Three things to know:

- **Saving requires an OpenACP restart.** The adapter reads its settings once at startup. Use
  the **Restart OpenACP** button on the page — it asks for confirmation and tells you how many
  agent sessions the restart would terminate.
- **The hook is lost when the Discord adapter is reinstalled or updated.** Use *Redeploy hook*
  on the page (or `npm run install-hook` in `openacp-channel-bindings/`), then restart OpenACP.
  A `422` from that endpoint means the module is not built — run `npm run build` there.
- **OpenACP itself is not part of this repository.** On a freshly copied PC, the *OpenACP
  installation* card installs `@openacp/cli` + `@openacp/discord-adapter` globally via npm (same as
  `npm install -g @openacp/cli @openacp/discord-adapter`). It does not create the OpenACP workspace
  or set the Discord bot token — those stay manual.

Writes are guarded: the workspace directory must exist, channel IDs must be Discord snowflakes,
the file is written atomically with a timestamped backup, and a revision check rejects the save
if something else changed the file in the meantime.

## System page — fresh-PC setup & screenshots

The **System** page in the dashboard groups the "install a dependency from a button" helpers.

- **Screenshots (Python / mss).** Installs the [`mss`](https://pypi.org/project/mss/) library into
  the backend venv (`pip install mss`) and captures the **primary monitor of the PC the backend
  runs on** to a PNG shown right on the page. Captures are saved under `backend/screenshots/`
  (gitignored).

  | Endpoint | Purpose |
  | --- | --- |
  | `GET /api/system/screenshot/status` | Whether `mss` is installed, and its version |
  | `POST /api/system/screenshot/install` | `pip install mss` into the backend venv (write token) |
  | `POST /api/system/screenshot/capture` | Capture the primary monitor, return the PNG's URL (write token) |
  | `GET /api/system/screenshot/file/{name}` | Serve a captured PNG (filename pattern-validated, no traversal) |

- **Prerequisites (Python / Node).** These **cannot** be installed from the dashboard — it is
  itself a Python + Node app, so both must exist before it runs. On a fresh PC, double-click
  `install-agent-hub-prerequisites.bat` in the repository root: it installs Python 3.12+,
  Node 20+ and PowerShell 7 via winget, then runs `scripts\setup.ps1`.

## Moving to another PC

Copying the folder alone does **not** work: `backend\.venv` hard-codes absolute paths,
`node_modules` is platform-bound, and OpenACP + its workspace live outside the repository.
The path is:

1. **Before copying**, on the source PC's dashboard OpenACP page, click *Copy settings.json here* —
   this writes the live OpenACP settings (**Discord bot token included**) into `openacp-config/`
   inside the repo. That folder is **gitignored**; it must never be committed.
2. Copy the repository.
3. Double-click `install-agent-hub-prerequisites.bat` (installs Python, Node and PowerShell 7 via
   winget, then runs `setup.ps1` — recreates the venv, installs `node_modules`, creates `.env`).
4. Start Agent Hub (`start-agent-hub.bat`).
5. On the dashboard's **OpenACP** page, click *Install OpenACP*.
6. Click *Apply bundle to this PC* to restore the OpenACP settings from `openacp-config/`
   (the previous file, if any, is kept as `settings.json.pre-import.bak`), then restart OpenACP.
7. Make sure the bound workspace folders (e.g. `C:\unity\*`) exist on the new PC, or OpenACP drops
   those bindings.

> **The `openacp-config/` bundle carries the Discord bot token in plain text.** It travels inside
> the copied folder on purpose, but is gitignored so it cannot be committed. Move it on physical
> media between your own machines — never over the internet.

## Send a clean copy to someone else

To hand Agent Hub to another person without any of your data, build a shareable zip:

```powershell
pwsh -File .\scripts\make-distributable.ps1            # -> Desktop\agent-hub.zip
pwsh -File .\scripts\make-distributable.ps1 -OutDir D:\out
pwsh -File .\scripts\make-distributable.ps1 -NoZip     # leaves a folder instead
```

It copies source only and **leaves out** `.env`, `openacp-config/` (the bot-token bundle),
`agent_hub.db` (your tasks), and all regenerated folders (`.venv`, `node_modules`, `.next`, caches,
`.git`, `.claude`). A `START-HERE.txt` is added for the recipient. They unzip it, double-click
`install-agent-hub-prerequisites.bat`, then `start-agent-hub.bat`, and set up **their own** Discord
bot — nothing of yours travels in the zip (verify: it contains `.env.example`, never `.env`, and no
bot token).

## Security limitations (V1)

- The backend **must remain bound to localhost** unless protected by a secure private network.
- Set `AGENT_HUB_WRITE_TOKEN` — with an empty token all writes are open (dev mode only).
- **Secrets must not be committed** (`.env` is gitignored); the token is never logged.
- Agent Hub stores **no** Claude, OpenAI or Discord credentials.
- There is no user management/registration and API payloads are never executed as commands.
  The exceptions run a fixed command with a fixed argument list — no shell, no user-supplied
  input, a timeout, and a write token: `POST /api/openacp/redeploy` and
  `POST /api/openacp/daemon/{restart,stop}` (`node scripts/install-hook.mjs`, `openacp
  restart|stop`), `POST /api/openacp/install` (`npm install -g @openacp/cli
  @openacp/discord-adapter`), and `POST /api/system/screenshot/install` (`pip install mss`).
- `AGENT_HUB_OPENACP_SETTINGS_PATH` points at a file that **contains the Discord bot token**.
  The API exposes only its `channelBindings` key. Backups written to
  `AGENT_HUB_OPENACP_SETTINGS_BACKUP_DIR` are full copies of that file — they default to
  `~/.agent-hub/settings-backups`, outside the repository, and **must be kept out of version
  control**.
- Deleting an artifact removes only the database record — files on disk are never deleted.
- **Agents must not be given permission to merge or push directly to the default branch**;
  the reporting templates instruct them to work on `agent/rem-###-*` branches.

## SQLite database backup

The database lives at **`backend\agent_hub.db`**. To back it up, stop the backend and copy
the file:

```powershell
Copy-Item C:\agent-hub\backend\agent_hub.db "D:\Backups\agent_hub-$(Get-Date -Format yyyyMMdd-HHmm).db"
```

(While the backend is running, prefer `sqlite3 agent_hub.db ".backup backup.db"` if you have
the sqlite3 CLI, or simply stop the backend first.)

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `agent-report` reports connection error (exit 3) | Backend not running — `.\scripts\start-backend.ps1`; check `AGENT_HUB_URL`. |
| `401 Missing bearer token` | Set `AGENT_HUB_WRITE_TOKEN` in your shell/environment to match the backend `.env`. |
| Dashboard shows "Backend offline" | Backend not running or wrong port; check <http://127.0.0.1:8765/api/health>. |
| Dashboard actions fail with 401 | Set `NEXT_PUBLIC_AGENT_HUB_WRITE_TOKEN` in `frontend\.env.local` and restart the frontend. |
| `alembic upgrade head` fails right after copying to a new PC | The copied `backend\.venv` points at the old PC's Python. Delete it and re-run `.\scripts\setup.ps1`. |
| `alembic upgrade head` fails on an old DB | Back up `backend\agent_hub.db`, then investigate with `alembic current` / `alembic history`. |
| *Redeploy hook* returns `422` | The channel-bindings module is not built — `cd openacp-channel-bindings; npm run build`. |
| Worker shows *offline (stale)* | No heartbeat within `AGENT_HUB_WORKER_STALE_SECONDS` (1200s); check the **AgentHub Heartbeat** task. If you shorten the threshold, shorten the task interval with it. |
| `agent-report` not found after install | Restart the terminal (PATH change), or re-run `.\scripts\install-agent-report.ps1`. |
| `ModuleNotFoundError: No module named 'agent_report'` (command starts, then dies) | A `pip install --user` copy is being used; agents disable user-site. Re-run `.\scripts\install-agent-report.ps1`, which installs into the venv and removes the `--user` copy. |

## Repository layout

```text
backend/    FastAPI app (app/models, app/schemas, app/routers, app/services), Alembic, tests
frontend/   Next.js dashboard (app/, components/, lib/, types/)
cli/        agent-report package + tests
templates/  CLAUDE_REPORTING.md, AGENTS_REPORTING.md
scripts/    setup.ps1, start-backend.ps1, start-frontend.ps1, start-all.ps1, stop-all.ps1,
            restart-openacp.ps1, install-agent-report.ps1, heartbeat.ps1,
            heartbeat-silent.vbs, cleanup-openacp-tunnels.ps1, make-distributable.ps1,
            lib.ps1 (helpers shared by the scripts above)
start-agent-hub.bat        Double-click launcher (backend + dashboard + OpenACP)
stop-agent-hub.bat         Double-click stopper
openacp-channel-bindings/  Discord channel -> project bindings for the OpenACP adapter (TS + vitest)
```
