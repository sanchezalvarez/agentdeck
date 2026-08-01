# Agent Deck

Run **Claude Code** and **Codex** agents from Discord, and watch what they do on a local
dashboard. Agents are driven remotely through [OpenACP](https://www.npmjs.com/package/@openacp/cli);
while they work they report progress back over a small CLI, so you can follow — and approve —
their work from your phone.

Everything runs on your own machine. No cloud service, no Docker, no telemetry.

```text
Discord ⇄ OpenACP ⇄ Claude Code / Codex agents (local PC)
                          │
                          │  agent-report CLI (HTTP)
                          ▼
             FastAPI backend (127.0.0.1:8765)
                 │ SQLite + SSE live updates
                 ▼
             Next.js dashboard (http://localhost:3000)
```

**One Discord channel = one project**, with a fixed agent and workspace. Every thread in that
channel becomes its own agent session, created from the first message. Agents finish successful
work as `needs_review` — only a human approval in the dashboard marks a task `completed`.

## Requirements

Windows 11, Python 3.12+, Node.js 20+. The installer below sets up Python, Node and
PowerShell 7 for you if they are missing.

## Install

```powershell
git clone https://github.com/sanchezalvarez/agentdeck.git
cd agentdeck
```

Then double-click **`agent-deck.bat`** and pick **Install**. It installs anything missing via
winget, creates the Python venv, installs dependencies and writes a starter `.env`.

## Run

Double-click **`start-agent-deck.bat`** — it starts the backend, the dashboard and OpenACP, then
opens <http://localhost:3000>. Running it twice is safe; it leaves anything already running
alone. **`stop-agent-deck.bat`** shuts everything down.

Both are shortcuts for **`agent-deck.bat`**, which shows a start / stop / install menu when you
double-click it.

The same file takes the action as an argument, which is what you want in a shortcut or a
scheduled task:

```powershell
.\agent-deck.bat start      # also: -NoBrowser, -DryRun
.\agent-deck.bat stop
.\agent-deck.bat install
```

## Connect Discord

Agent Deck does not ship a Discord bot — you use your own.

1. Open the **OpenACP** page in the dashboard and click **Install OpenACP**.
2. Create a Discord bot and point OpenACP at it, then map channels to projects on the same page.
   Details: [`openacp-channel-bindings/README.md`](openacp-channel-bindings/README.md).
3. Restart OpenACP. The adapter reads its settings only at startup.

## Let agents report their work

Install the reporting CLI, then copy the matching template into each project you want tracked:

```powershell
.\scripts\install-agent-report.ps1
```

- Claude Code project → copy [`templates/CLAUDE_REPORTING.md`](templates/CLAUDE_REPORTING.md)
  into its `CLAUDE.md`
- Codex project → copy [`templates/AGENTS_REPORTING.md`](templates/AGENTS_REPORTING.md)
  into its `AGENTS.md`

Fill in the `<PROJECT_SLUG>`, `<TEST_COMMAND>`, `<BUILD_COMMAND>` and `<DEFAULT_BRANCH>`
placeholders. From then on agents create tasks, post milestones and finish with a summary that
lands in the dashboard — and optionally in a Discord channel.

## Configuration

Copy `.env.example` to `.env` (the installer does this). The one setting you should not skip:

```ini
AGENT_DECK_WRITE_TOKEN=      # empty = every write endpoint is open
```

Generate one with `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
Every other variable has a working default — the full table is in
[AGENTS.md](AGENTS.md#environment-variables).

## Security

This is a **local-only** application and its defaults assume that:

- Keep the backend bound to `127.0.0.1`. It has no user accounts and read-only endpoints are
  unauthenticated.
- Set `AGENT_DECK_WRITE_TOKEN`, or anything that reaches the port can write.
- Agent Deck stores no Claude, OpenAI or Discord credentials — but your **OpenACP settings file
  holds your Discord bot token**. Never commit it. `openacp-config/` is gitignored for this reason.
- Don't grant agents permission to push to your default branch; the reporting templates keep
  them on `agent/rem-###-*` branches.

Full list, including exactly which endpoints run a subprocess:
[AGENTS.md](AGENTS.md#security-limitations-v1).

## Documentation

| | |
| --- | --- |
| [AGENTS.md](AGENTS.md) | Working reference: every script, endpoint, env var, CLI example, and troubleshooting |
| [`openacp-channel-bindings/README.md`](openacp-channel-bindings/README.md) | How Discord channels map to projects |
| [`templates/`](templates/) | Reporting instructions to drop into your projects |

## License

MIT — see [LICENSE](LICENSE).

`@openacp/cli` and `@openacp/discord-adapter` are separate third-party packages installed from
npm; they are not part of this repository and carry their own licenses.
