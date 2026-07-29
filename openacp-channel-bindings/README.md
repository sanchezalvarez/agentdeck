# openacp-channel-bindings

Fixed **Discord channel → OpenACP project** bindings for `@openacp/discord-adapter`.

One Discord channel represents one project with a **fixed agent and workspace**. Every thread
inside that channel is one separate OpenACP session, created automatically from the first
message. Nobody types `/new <agent> <workspace>` any more.

## Why this is a separate module

`@openacp/discord-adapter` is published as **compiled JavaScript only** — `package.json` sets
`files: ["dist"]`, there are no sourcemaps, and the upstream repository
(`github.com/Open-ACP/discord-adapter`) returns *Repository not found*. There is no source
tree to modify.

So the feature lives here as a normal, buildable, tested TypeScript module, and a
**minimal patch** (one import + four lines) is applied to the adapter's `messageCreate`
handler by `scripts/install-hook.mjs`. All logic is in this repository; the adapter only calls
into it.

**Consequence:** the patch is lost whenever the plugin is reinstalled or updated. Re-run
`npm run install-hook` after every `openacp plugin update @openacp/discord-adapter`.

## Configuration

> **Easier route:** the Agent Hub dashboard has an **OpenACP** page that edits these bindings
> for you (add/remove project channels, agent dropdown, workspace validation) and can re-apply
> the hook with a button. The manual JSON route below still works and is the source of truth.

Add `channelBindings` to the adapter's plugin settings:

```text
%USERPROFILE%\openacp-workspace\.openacp\plugins\data\@openacp\discord-adapter\settings.json
```

```json
{
  "channelBindings": {
    "DISCORD_CHANNEL_ID_CROWFORGE": {
      "agent": "claude",
      "workspace": "D:\\Projects\\CrowForge"
    },
    "DISCORD_CHANNEL_ID_UNITY": {
      "agent": "claude",
      "workspace": "C:\\Unity\\MyGame"
    },
    "DISCORD_CHANNEL_ID_WEB": {
      "agent": "codex",
      "workspace": "D:\\Projects\\Web"
    }
  }
}
```

Keep the existing keys (`botToken`, `guildId`, `forumChannelId`, …) — add `channelBindings`
alongside them. Windows paths need doubled backslashes in JSON.

### Validation rules

| Rule | Behaviour when violated |
| --- | --- |
| Key must be a numeric Discord snowflake (17–20 digits) | Entry dropped, error logged |
| `agent` must be a non-empty string | Entry dropped, error logged |
| `workspace` must be a non-empty string | Entry dropped, error logged |
| `workspace` must be an existing directory | Entry dropped, error logged; messages in that channel are ignored |

One broken entry never disables the other project channels.

## Setup

```powershell
cd C:\agent-hub\openacp-channel-bindings
npm install
npm run verify        # tsc build + vitest
npm run install-hook  # copy compiled module into the adapter + patch adapter.js
```

Then:

1. In Discord, enable **Developer Mode** (User Settings → Advanced).
2. Right-click each project channel → **Copy Channel ID**.
3. Paste the IDs into `channelBindings` in `settings.json` (path above).
4. Restart OpenACP.

Useful flags:

```powershell
node scripts/install-hook.mjs --check    # is the hook installed? (exit 0 = yes, 2 = no)
node scripts/install-hook.mjs --revert   # remove the patch from adapter.js
node scripts/install-hook.mjs --adapter <path-to-dist>
```

## Text-channel workflow

1. Create a normal text channel, e.g. `#crowforge`, and bind it in `channelBindings`.
2. In that channel, start a **thread** (message → *Create Thread*, or the `#` thread button).
3. Send the first message in the thread → an OpenACP session is created automatically with
   the channel's fixed agent and workspace.
4. Every further message in that thread continues **the same** session.
5. A second thread in the same channel = a second independent session, same project.

## Forum-channel workflow

1. Create a forum channel, e.g. `#unity-tasks`, and bind it in `channelBindings`.
2. Create a **post** in the forum — the post *is* the thread.
3. The first message in the post creates the session; further messages continue it.
4. Each post is a separate session against the same fixed agent and workspace.

Text threads and forum posts need no separate configuration: in both cases Discord reports the
project channel as the thread's `parentId`, which is what the binding is keyed on.

## Behaviour guarantees

- **Agent and workspace cannot be overridden** inside a bound channel — they come from
  configuration only; `/new` arguments never reach this path.
- **Messages outside configured channels are untouched.** Slash commands, approvals,
  streaming, attachments, cancellation and the existing `openacp-sessions` forum workflow all
  behave exactly as before.
- **`/new` still works** everywhere, unchanged.
- **The assistant thread is never hijacked**, even if its parent channel is bound.
- **Mapping survives restart.** The thread → session link is written into OpenACP's own
  session store via `sessionManager.patchRecord()`, alongside the agent, workspace and parent
  channel ID; `getSessionByThread()` restores it after a restart. Nothing is held only in
  adapter memory.
- **Concurrent first messages** in a fresh thread create exactly one session.

## Logs

All entries are prefixed `[discord-bindings]` and go through the adapter's own logger.

| Event | Level |
| --- | --- |
| `Channel bindings loaded` | info |
| `Binding resolved` | debug |
| `Session created for bound project thread` | info |
| `Existing session resumed` | info |
| `Invalid channel binding — entry ignored` | error |
| `Message arrived in a channel with an invalid binding — ignoring` | error |
| `Failed to create session for bound project thread` | error |
| `Thread is not inside a configured project channel — ignoring` | debug |

Logs land in `%USERPROFILE%\openacp-workspace\.openacp\logs\openacp.log`. Set
`logging.level` to `debug` in `.openacp\config.json` to see the debug lines.

## How it hooks in

The patch sits in `adapter.js` → `setupMessageHandler`, immediately after the existing session
lookup and **before** attachment processing, so files attached to a thread's first message are
stored against the real session ID:

```js
let sessionId = this.core.sessionManager.getSessionByThread("discord", threadId)?.id ?? "unknown";
// openacp-channel-bindings: auto-create/resume the session bound to this project thread
if (sessionId === "unknown") {
    sessionId = (await __channelBindings.ensureBoundSession(this, message, log)) ?? "unknown";
}
```

Session creation reuses the exact path `/new` uses (`commands/new-session.js`):

```js
const session = await core.handleNewSession('discord', agent, workspace);
await core.sessionManager.patchRecord(session.id, { platform: { threadId, parentChannelId } });
```

The only difference is that the thread already exists — Discord created it when the user opened
the thread or forum post — so no thread is created here.

## Architecture

| File | Responsibility |
| --- | --- |
| `src/bindings.ts` | Config validation, memoised loading, parent-channel → binding resolution |
| `src/session-link.ts` | Find-or-create the session for a thread; persist the mapping; race guard |
| `src/adapter-hook.ts` | Thin adapter-facing entry point; workspace existence check |
| `src/types.ts` | Shared types (no discord.js / plugin-sdk dependency) |
| `scripts/install-hook.mjs` | Build output → adapter, idempotent patch, `--check` / `--revert` |
| `backup/dist-20260719/` | Verbatim copy of the adapter's original `dist` |

Nothing imports `discord.js` or `@openacp/plugin-sdk`: the adapter, core and message objects
are duck-typed, so the whole module is unit-testable without a live Discord connection. The
adapter passes its own `log` instance into the hook.

## Tests

```powershell
npm test
```

22 tests, covering the required scenarios:

- text-channel thread binding
- forum thread binding
- automatic session creation
- session reuse across follow-up messages
- persistence after an OpenACP restart
- unknown / unconfigured channel
- invalid (missing) workspace

plus: separate sessions per thread, concurrent first messages, assistant-thread protection,
inert behaviour when unconfigured, session-creation failure, and config validation edge cases.

## Restoring the adapter

```powershell
Copy-Item C:\agent-hub\openacp-channel-bindings\backup\dist-20260719\* `
  "$env:APPDATA\npm\node_modules\@openacp\discord-adapter\dist" -Recurse -Force
```
