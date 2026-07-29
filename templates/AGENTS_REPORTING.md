# Agent Hub Reporting (copy into project AGENTS.md)

<!--
Copy this whole section into the project's AGENTS.md (Codex CLI) and replace:
  <PROJECT_SLUG>        e.g. crowforge
  <TEST_COMMAND>        e.g. pytest   or   npm test
  <BUILD_COMMAND>       e.g. npm run build   or   dotnet build
  <TYPECHECK_COMMAND>   e.g. npm run typecheck   or   mypy .
  <DEFAULT_BRANCH>      e.g. main
-->

## Context

You are being controlled remotely through Discord via OpenACP. Every real task has a
`REM-###` task ID in the local Rembrosoft Agent Hub. Report your work through the globally
installed `agent-report` CLI. Reporting complements — it does not replace — your final
Discord response.

Project slug: `<PROJECT_SLUG>`
Default branch: `<DEFAULT_BRANCH>` — **never push to it or merge into it.** Work on an
`agent/rem-###-short-name` branch.

## Expected workflow

```text
1. Inspect task and repository.
2. Call agent-report start.
3. Perform the work.
4. Report only major milestones.
5. Run tests, type checks and builds relevant to the project.
6. Review modified files and Git diff.
7. Call agent-report finish, fail or block.
8. Send the final response in Discord.
```

## Rules

- Report meaningful lifecycle events only — no progress spam (one event per completed
  sub-goal, not per file edit).
- Before finishing, run the project's validation: `<TEST_COMMAND>`, `<TYPECHECK_COMMAND>`,
  `<BUILD_COMMAND>`.
- **Never claim tests passed if tests were not run** — report `--tests not_run` instead.
- Never push or merge into `<DEFAULT_BRANCH>`.
- Report blocked or failed work honestly (`agent-report block` / `agent-report fail`).
- Successful work must end with `agent-report finish`; the task becomes `needs_review`.
- If `agent-report` is unavailable or fails, **say so plainly and stop reporting**. Never write
  your own wrapper script or fallback path: a silent workaround records the work nowhere, so
  you would be reporting success into a void while the dashboard shows nothing.
  Only a human can approve it to `completed` in the dashboard.

## Exact commands

```powershell
# 1. Start
agent-report start `
  --task REM-104 `
  --agent codex `
  --project <PROJECT_SLUG> `
  --branch agent/rem-104-short-name `
  --working-directory "$PWD"

# 2. Milestone
agent-report progress --task REM-104 --message "Implemented table style parsing"

# 3. Tests / build
agent-report testing --task REM-104 --kind tests --status started
agent-report testing --task REM-104 --kind tests --status passed --message "42 tests passed"
agent-report testing --task REM-104 --kind build --status passed

# 4a. Success → needs_review
agent-report finish `
  --task REM-104 `
  --summary "Implemented DOCX table import fixes and added tests." `
  --branch "agent/rem-104-short-name" `
  --commit "a94c2e1" `
  --tests passed `
  --build passed `
  --exit-code 0

# 4b. Failure
agent-report fail `
  --task REM-104 `
  --error "Backend tests failed because a fixture is missing." `
  --tests failed `
  --build not_run `
  --exit-code 1

# 4c. Blocked
agent-report block --task REM-104 --reason "Missing client test document."

# Optional artifact
agent-report artifact `
  --task REM-104 `
  --type screenshot `
  --name "Imported document preview" `
  --path "D:\AgentWorkspaces\artifacts\preview.png"
```
