# Agent Deck Reporting (copy into project CLAUDE.md)

<!--
Copy this whole section into the project's CLAUDE.md and replace the placeholders:
  <PROJECT_SLUG>        e.g. crowforge
  <TEST_COMMAND>        e.g. pytest   or   npm test
  <BUILD_COMMAND>       e.g. npm run build   or   dotnet build
  <TYPECHECK_COMMAND>   e.g. npm run typecheck   or   mypy .
  <DEFAULT_BRANCH>      e.g. main
-->

## Context

You are being controlled remotely through Discord via OpenACP. Every real task you work on
has a task ID in the form `REM-###` in the local Agent Deck. You must report your
work to the Agent Hub using the `agent-report` CLI (already installed globally). The Agent Hub
is a local monitoring tool — reporting to it does not replace your final Discord response.

Project slug: `<PROJECT_SLUG>`
Default branch: `<DEFAULT_BRANCH>` — **never push to it or merge into it.** Work on a
`agent/rem-###-short-name` branch.

## Expected workflow

```text
1. Inspect the task and repository.
2. Call agent-report start.
3. Perform the work.
4. Report only major milestones with agent-report progress.
5. Run tests, type checks and builds relevant to the project.
6. Review modified files and the Git diff.
7. Call agent-report finish, fail or block.
8. Send the final response in Discord.
```

## Rules

- Report meaningful lifecycle events; do **not** spam progress events. A handful of major
  milestones per task is enough (roughly one per completed sub-goal, not per file edit).
- Run relevant validation before finishing: `<TEST_COMMAND>`, `<TYPECHECK_COMMAND>`,
  `<BUILD_COMMAND>`.
- **Never claim tests passed if tests were not run.** Use `--tests not_run` honestly.
- Never push or merge into `<DEFAULT_BRANCH>`.
- Report blocked or failed work honestly with `agent-report block` / `agent-report fail`.
- A successful implementation must end with `agent-report finish` — the task then becomes
  `needs_review`. You never mark a task completed; a human approves it in the dashboard.
- If `agent-report` is unavailable or fails, **say so plainly and stop reporting**. Never write
  your own wrapper script or fallback path: a silent workaround records the work nowhere, so
  you would be reporting success into a void while the dashboard shows nothing.

## Exact commands

Start (right after you understand the task):

```powershell
agent-report start `
  --task REM-104 `
  --agent claude `
  --project <PROJECT_SLUG> `
  --branch agent/rem-104-short-name `
  --working-directory "$PWD"
```

Progress (major milestones only):

```powershell
agent-report progress --task REM-104 --message "Implemented table style parsing"
```

Tests / build:

```powershell
agent-report testing --task REM-104 --kind tests --status started
# ... run <TEST_COMMAND> ...
agent-report testing --task REM-104 --kind tests --status passed --message "42 tests passed"

agent-report testing --task REM-104 --kind build --status started
# ... run <BUILD_COMMAND> ...
agent-report testing --task REM-104 --kind build --status passed
```

Finish (success → needs_review):

```powershell
agent-report finish `
  --task REM-104 `
  --summary "Implemented DOCX table import fixes and added tests." `
  --branch "agent/rem-104-short-name" `
  --commit "a94c2e1" `
  --tests passed `
  --build passed `
  --exit-code 0
```

Fail (honest failure report):

```powershell
agent-report fail `
  --task REM-104 `
  --error "Backend tests failed because a fixture is missing." `
  --tests failed `
  --build not_run `
  --exit-code 1
```

Block (you need input from a human):

```powershell
agent-report block --task REM-104 --reason "Missing client test document."
```

Attach an artifact (screenshot, log, report):

```powershell
agent-report artifact `
  --task REM-104 `
  --type screenshot `
  --name "Imported document preview" `
  --path "D:\AgentWorkspaces\artifacts\preview.png"
```
