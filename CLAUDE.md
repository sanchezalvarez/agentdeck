# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Agent Deck is a **local-only** Windows app that records and displays work done by Claude Code /
Codex agents driven from Discord through OpenACP. [README.md](README.md) is the pitch;
[AGENTS.md](AGENTS.md) is the full operational reference (every script, endpoint, env var,
CLI example, troubleshooting table) — read it before changing scripts, OpenACP integration or
deployment behaviour.

## Commands

All commands assume PowerShell from the repository root (`C:\agent-hub`).

```powershell
.\scripts\setup.ps1              # venv + all deps + builds channel bindings + creates .env
.\agent-deck.bat start           # backend + dashboard + OpenACP (also: stop | install)
                                 # start-agent-deck.bat / stop-agent-deck.bat = double-click shortcuts
.\scripts\start-backend.ps1      # alembic upgrade head, then FastAPI on 127.0.0.1:8765
.\scripts\start-frontend.ps1     # Next.js on localhost:3000
```

Tests and checks:

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest
cd cli;      ..\backend\.venv\Scripts\python.exe -m pytest      # CLI shares the backend venv
cd frontend; npm run lint; npm run typecheck; npm run build
cd openacp-channel-bindings; npm run verify                     # tsc build + vitest

# single test / single case
..\backend\.venv\Scripts\python.exe -m pytest tests\test_tasks.py::test_finish_results_in_needs_review
cd openacp-channel-bindings; npx vitest run src/__tests__/bindings.test.ts
```

Schema changes go through Alembic — the app never calls `create_all` (only the test fixture does):

```powershell
cd backend; .\.venv\Scripts\python.exe -m alembic revision --autogenerate -m "..."
cd backend; .\.venv\Scripts\python.exe -m alembic upgrade head
cd backend; .\.venv\Scripts\python.exe -m app.seed     # optional sample data, skips a non-empty DB
```

## Architecture

```
Discord ⇄ OpenACP ⇄ Claude Code / Codex agents  →  agent-report CLI (HTTP)
                                                   →  FastAPI :8765 (SQLite + SSE)
                                                   →  Next.js dashboard :3000
```

Four independent pieces, all talking over HTTP — nothing shares a process or a database handle:

- **backend/** — FastAPI + SQLModel + SQLite + Alembic. Routers under `/api` are thin; all
  lifecycle logic lives in `app/services/task_service.py`. Every mutation follows the same shape:
  mutate the `Task`, append a `TaskEvent` via `add_event()`, commit, then `publish_task_event()`
  onto the in-process SSE broadcaster.
- **cli/** — `agent-report`, the only interface agents use. It talks **exclusively to the HTTP
  API**, never to SQLite. Exit codes are part of its contract: `0` ok, `1` API error,
  `2` bad arguments, `3` connection error.
- **frontend/** — Next.js App Router, TypeScript strict. Pages are client components that fetch
  through `lib/api.ts` and subscribe via `useLive()` (`lib/use-live.ts`), which falls back to
  10s polling when the SSE stream drops.
- **openacp-channel-bindings/** — standalone TypeScript module (vitest) that maps a Discord
  channel to a project. `@openacp/discord-adapter` ships compiled JS only, so
  `scripts/install-hook.mjs` patches four lines into its `messageCreate` handler and all logic
  stays here.

### Invariants worth knowing before you change behaviour

- **Agents never mark work `completed`.** `finish` sets `needs_review`; only a human approval
  (`POST /api/tasks/{id}/approve`) reaches `completed`. Don't add a path that skips review.
- **Task IDs are sequential and public:** `REM-001`, `REM-002`, … allocated by
  `next_public_id()` with a 3-attempt retry on the unique constraint. `resolve_task()` accepts
  either the `REM-###` form or the numeric primary key; endpoints take `{task_identifier}`.
- **Terminal statuses reject further agent activity** (`ensure_not_terminal()` → 409). The
  status sets live in `app/models/enums.py`; `event_type` is deliberately an open string
  (`KNOWN_EVENT_TYPES` documents the used ones rather than constraining them).
- **Every write endpoint carries `dependencies=[WriteAuth]`** — bearer `AGENT_DECK_WRITE_TOKEN`,
  compared with `secrets.compare_digest`. An empty token means open writes (dev only). GETs are
  unauthenticated by design. New mutating endpoints must add `WriteAuth`.
- **Agent Deck never starts or stops Claude Code / Codex.** It *does* control the OpenACP daemon
  and the adapter's config — those are the only endpoints that spawn a subprocess
  (`/api/openacp/{redeploy,install,daemon/restart,daemon/stop,agents/{id}/install}`,
  `/api/system/screenshot/install`). They run a fixed command with a fixed argument list, no
  shell, with a timeout. Keep it that way. `agents/{id}/install` validates `id` against
  `openacp_daemon.AGENT_CATALOG` first — the argv is fixed only because the id is.
  A *foreground* OpenACP instance writes no pid file, so the daemon endpoints shell out to
  `scripts\{restart,stop}-openacp.ps1` for it — the script name comes from `FOREGROUND_SCRIPTS`
  in `openacp_daemon.py`, never from the request.
- **The OpenACP npm packages are pinned** (`openacp_install.py`). `install-hook.mjs` patches the
  adapter's compiled `adapter.js` by matching exact code anchors, so an unpinned `latest` can
  break Discord bindings on a fresh install. Version bumps go together with the anchors.
- **The OpenACP settings file contains the Discord bot token.** The API exposes only its
  `channelBindings` key; backups are full copies and therefore default to `~/.agent-deck/`,
  outside the repository. `openacp-config/`, `.env` and `backend/agent_deck.db` are gitignored —
  `scripts/make-distributable.ps1` exists to prove a shareable zip carries none of them.
- **Discord summaries are fire-and-forget** on a daemon thread (`services/discord_notify.py`) —
  a failing webhook must never make `agent-report finish` fail. The backend forwards the agent's
  own text verbatim; no model rewrites it.

### Configuration

Settings are pydantic-settings with the `AGENT_DECK_` prefix, read from `../.env` relative to
`backend/` (see `app/config.py`, `.env.example`). `get_settings()` is `lru_cache`d — tests
monkeypatch the cached instance rather than the environment. Defaults that point outside the
repo (OpenACP workspace, backup dir) are resolved from `Path.home()`; defaults that point inside
it are resolved from `__file__`, so renaming the repo folder doesn't break them.

## Conventions

- **Frontend colour and sizing is a closed system.** `app/riso.css` holds the design tokens,
  `globals.css` maps them into Tailwind v4 via `@theme inline`. Components reference tokens —
  never raw hex, never `#fff`/`#000`. Control heights, spacing and animation values are fixed in
  `.claude/skills/risograph-ui/DESIGN_RULES.md`; change a value there and in `riso.css`, not in a
  component. Fonts are bundled via `@fontsource` because the dashboard must work offline.
- **Windows line endings matter.** `.gitattributes` forces CRLF on `.bat`, `.cmd`, `.vbs` and
  `.ps1` — `cmd.exe` mis-parses `goto` labels in an LF-only batch file.
- **PowerShell scripts share `scripts/lib.ps1`**; `agent-deck.bat` owns the launcher dispatch and
  passes any trailing arguments straight through. `start-agent-deck.bat` / `stop-agent-deck.bat`
  are double-click shortcuts that `call` it — keep them free of logic.
- **`agent-report` is installed into `backend\.venv`, never with `pip install --user`** — agent
  processes run with user-site disabled, so a `--user` install fails at import. Re-run
  `scripts\install-agent-report.ps1` after rebuilding the venv (the launcher hard-codes its path).
- Backend tests use an in-memory SQLite engine with `StaticPool` and override `get_session`; the
  `client` fixture blanks `discord_summary_webhook` so a test run can never post to a real
  Discord channel. Keep that guard when adding fixtures.
