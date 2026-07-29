# Agent Deck — implementačný plán (V1)

Lokálna aplikácia na evidenciu a kontrolu práce Claude Code / Codex agentov riadených cez Discord + OpenACP.
Agent Deck **iba zaznamenáva a zobrazuje** — neriadi agentov ani OpenACP.

## Komponenty

1. **backend/** — FastAPI + SQLModel + SQLite + Alembic, beží na `127.0.0.1:8765`.
   - Modely: Project, Worker, Task, TaskEvent, Artifact.
   - Sekvenčné verejné ID úloh `REM-001…`.
   - Lifecycle endpointy (start/progress/testing/finish/fail/block/cancel/approve/reject/archive).
   - Úspešné dokončenie agentom → `needs_review`; `completed` až po manuálnom schválení.
   - Zápisy chránené `Authorization: Bearer <AGENT_HUB_WRITE_TOKEN>`.
   - SSE stream `/api/events/stream` s keep-alive.
2. **cli/** — `agent-report` (argparse + httpx), komunikuje výhradne cez HTTP API.
3. **frontend/** — Next.js (App Router, TS strict, Tailwind, shadcn-štýl komponenty).
   Stránky: Overview, Tasks, Task detail, Projects, Workers. SSE + polling fallback.
4. **templates/** — CLAUDE_REPORTING.md, AGENTS_REPORTING.md (kopírovateľné inštrukcie pre agentov).
5. **scripts/** — setup.ps1, start-backend.ps1, start-frontend.ps1, start-all.ps1, install-agent-report.ps1.
6. **Seed** — `python -m app.seed` (manuálne, nikdy automaticky).

## Poradie prác

1. Backend konfigurácia + modely + schémy
2. Alembic + iniciálna migrácia
3. Services + routery + SSE
4. Backend testy (pytest)
5. CLI + testy
6. Šablóny inštrukcií
7. Frontend + SSE live updates
8. PowerShell skripty + seed
9. README + finálna validácia (pytest, lint, typecheck, build, E2E flow)

## Bezpečnostné zásady

- Bind iba na localhost, úzke CORS (`http://localhost:3000`).
- Žiadne mazanie súborov z disku, žiadne spúšťanie príkazov z API, žiadne cudzie credentials.
- Token sa nikdy neloguje.
