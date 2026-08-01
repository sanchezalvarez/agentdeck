#!/usr/bin/env node
/**
 * Installs the channel-binding hook into the installed @openacp/discord-adapter.
 *
 * The adapter is published as compiled JS only (no sources, no sourcemaps, and
 * the upstream repository is not public), so the feature ships as a separate
 * compiled module plus a minimal patch in the adapter's messageCreate handler.
 *
 * The script is idempotent and re-runnable: run it again after every
 * `openacp plugin update @openacp/discord-adapter`, which restores the
 * untouched dist and removes the hook.
 *
 * Usage:
 *   node scripts/install-hook.mjs [--adapter <path-to-dist>] [--check] [--revert]
 */

import { cpSync, existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const PROJECT = resolve(HERE, '..');
const BUILT = join(PROJECT, 'dist');

const MARKER = 'openacp-channel-bindings';
const IMPORT_LINE = `import * as __channelBindings from "./channel-bindings/index.js"; // ${MARKER}`;

const ANCHOR_IMPORT =
  'import { buildFallbackText, downloadDiscordAttachment, isAttachmentTooLarge, } from "./media.js";';

const ANCHOR_SESSION = `                const sessionId = this.core.sessionManager.getSessionByThread("discord", threadId)
                    ?.id ?? "unknown";`;

const PATCHED_SESSION = `                let sessionId = this.core.sessionManager.getSessionByThread("discord", threadId)
                    ?.id ?? "unknown";
                // ${MARKER}: auto-create/resume the session bound to this project thread
                if (sessionId === "unknown") {
                    sessionId = (await __channelBindings.ensureBoundSession(this, message, log)) ?? "unknown";
                }`;

/** Adapter release these patch anchors were written against. */
const EXPECTED_ADAPTER_VERSION = '2026.518.1';

function workspacePluginsDir() {
  const home = process.env.USERPROFILE || process.env.HOME;
  const workspace = process.env.OPENACP_WORKSPACE || (home ? join(home, 'openacp-workspace') : null);
  return workspace ? join(workspace, '.openacp', 'plugins') : null;
}

/**
 * The adapter is usually installed twice: once globally by npm, and once inside
 * the OpenACP workspace (.openacp/plugins/node_modules), which is the copy
 * OpenACP actually loads — .openacp/plugins/package.json lists it as a
 * dependency. Patching only the global copy silently does nothing, so every
 * installed copy is handled.
 *
 * Override with --adapter <path> (repeatable) or OPENACP_WORKSPACE.
 */
function defaultAdapterDists() {
  const candidates = [];
  const plugins = workspacePluginsDir();

  if (plugins) {
    candidates.push(join(plugins, 'node_modules', '@openacp', 'discord-adapter', 'dist'));
  }
  if (process.env.APPDATA) {
    candidates.push(
      join(process.env.APPDATA, 'npm', 'node_modules', '@openacp', 'discord-adapter', 'dist'),
    );
  }
  return candidates.filter((dir) => existsSync(join(dir, 'adapter.js')));
}

/**
 * The workspace copy is the one OpenACP loads. When the plugin manifest
 * declares the adapter but its dist is absent, patching the global copy alone
 * would report success and change nothing OpenACP ever reads — the exact
 * failure that makes Discord bindings look broken for no visible reason.
 *
 * Returns the missing dist path, or null when there is nothing to complain
 * about (no workspace yet, or the adapter is genuinely not a workspace plugin).
 */
function missingWorkspaceAdapter() {
  const plugins = workspacePluginsDir();
  if (!plugins) return null;

  const manifest = join(plugins, 'package.json');
  if (!existsSync(manifest)) return null;

  try {
    const pkg = JSON.parse(readFileSync(manifest, 'utf8'));
    if (!pkg?.dependencies?.['@openacp/discord-adapter']) return null;
  } catch {
    // An unreadable manifest is not evidence of a missing plugin.
    return null;
  }

  const dist = join(plugins, 'node_modules', '@openacp', 'discord-adapter', 'dist');
  return existsSync(join(dist, 'adapter.js')) ? null : dist;
}

function adapterVersion(distDir) {
  try {
    return JSON.parse(readFileSync(join(distDir, '..', 'package.json'), 'utf8')).version || 'unknown';
  } catch {
    return 'unknown';
  }
}

function parseArgs(argv) {
  const args = { check: false, revert: false, adapters: [] };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--check') args.check = true;
    else if (argv[i] === '--revert') args.revert = true;
    else if (argv[i] === '--adapter') {
      i += 1;
      if (argv[i]) args.adapters.push(argv[i]);
    }
  }
  return args;
}

function fail(msg) {
  console.error(`ERROR: ${msg}`);
  process.exit(1);
}

const args = parseArgs(process.argv.slice(2));
const explicit = args.adapters.length > 0;
const adapterDists = (explicit ? args.adapters : defaultAdapterDists()).map((dir) => resolve(dir));

// Only meaningful for the default search — an explicit --adapter is the
// caller's deliberate choice of what to patch.
const missingWorkspace = explicit ? null : missingWorkspaceAdapter();

if (adapterDists.length === 0) {
  fail('no installed discord-adapter found.\nPass an explicit path with --adapter <path>');
}

for (const dir of adapterDists) {
  if (!existsSync(join(dir, 'adapter.js'))) fail(`adapter.js not found in ${dir}`);
}

// ─── --check ────────────────────────────────────────────────────────────────
if (args.check) {
  let allPatched = true;
  for (const dir of adapterDists) {
    const patched = readFileSync(join(dir, 'adapter.js'), 'utf8').includes(MARKER);
    if (!patched) allPatched = false;
    console.log(`${patched ? 'INSTALLED    ' : 'NOT INSTALLED'}  ${dir}`);
  }
  if (missingWorkspace) {
    // Reported as not-installed: the patched global copy is not the one running.
    allPatched = false;
    console.log(`MISSING        ${missingWorkspace}`);
    console.log('The workspace plugin is declared but not installed — run "openacp plugin install');
    console.log('@openacp/discord-adapter", or reinstall OpenACP, then run this again.');
  }
  console.log(allPatched ? 'HOOK INSTALLED' : 'HOOK NOT INSTALLED');
  process.exit(allPatched ? 0 : 2);
}

// ─── --revert ───────────────────────────────────────────────────────────────
if (args.revert) {
  for (const dir of adapterDists) {
    const file = join(dir, 'adapter.js');
    const original = readFileSync(file, 'utf8');
    if (!original.includes(MARKER)) {
      console.log(`No hook to revert in ${dir}`);
      continue;
    }
    writeFileSync(
      file,
      original.replace(`${IMPORT_LINE}\n`, '').replace(PATCHED_SESSION, ANCHOR_SESSION),
      'utf8',
    );
    console.log(`Hook removed from ${file}`);
  }
  process.exit(0);
}

// ─── install ────────────────────────────────────────────────────────────────
if (!existsSync(join(BUILT, 'index.js'))) {
  fail('dist/ is missing — run "npm run build" first.');
}

for (const dir of adapterDists) {
  const target = join(dir, 'channel-bindings');
  mkdirSync(target, { recursive: true });
  cpSync(BUILT, target, { recursive: true });
  console.log(`Copied compiled module -> ${target}`);

  const file = join(dir, 'adapter.js');
  const original = readFileSync(file, 'utf8');

  if (original.includes(MARKER)) {
    console.log(`  adapter.js already patched — module refreshed, patch left as is.`);
    continue;
  }
  if (!original.includes(ANCHOR_IMPORT) || !original.includes(ANCHOR_SESSION)) {
    fail(
      `patch anchors not found in ${file}\n` +
        `  installed adapter: ${adapterVersion(dir)}\n` +
        `  hook written for:  ${EXPECTED_ADAPTER_VERSION}\n` +
        'Reinstall the pinned version (dashboard: OpenACP -> Install OpenACP), or update the\n' +
        'anchors in this script to match the new adapter.',
    );
  }

  writeFileSync(
    file,
    original
      .replace(ANCHOR_IMPORT, `${ANCHOR_IMPORT}\n${IMPORT_LINE}`)
      .replace(ANCHOR_SESSION, PATCHED_SESSION),
    'utf8',
  );
  console.log(`  Patched ${file}`);
}

if (missingWorkspace) {
  // Non-zero on purpose: the global copy is patched, but OpenACP loads the
  // workspace one, so nothing that matters actually changed.
  console.error(
    `\nERROR: the copy OpenACP loads is missing — ${missingWorkspace}\n` +
      'Only the global copy was patched, so Discord channel bindings will NOT work.\n' +
      'Install the workspace plugin ("openacp plugin install @openacp/discord-adapter"),\n' +
      'then run this again.',
  );
  process.exit(1);
}

console.log('\nDone. Restart OpenACP for the change to take effect.');
