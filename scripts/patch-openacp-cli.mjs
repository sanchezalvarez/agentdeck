#!/usr/bin/env node
/**
 * Fixes the @openacp/cli community-plugin loader so npm plugins load on Windows.
 *
 * The loader imports a plugin by absolute path:
 *
 *     const mod = await import(modulePath);          //  C:\...\dist\index.js
 *
 * Node's ESM loader rejects that on Windows — absolute paths must be file://
 * URLs — so *every* npm-installed plugin fails with ERR_UNSUPPORTED_ESM_URL_SCHEME
 * ("Received protocol 'c:'") and is skipped. @openacp/discord-adapter is an npm
 * plugin, so the symptom is a completely silent Discord: no startup notification,
 * no messages reaching agents, and "channels": [] in the daemon status, while the
 * adapter looks correctly installed everywhere you would think to check.
 *
 * The same bundle already does this correctly elsewhere (importFromDir uses
 * `import(pathToFileURL(entryPath).href)`), so the fix is to make the loader
 * match. pathToFileURL is a top-level import in the bundle and is correct on
 * every platform, so the patch is a no-op for POSIX behaviour.
 *
 * Upstream bug in @openacp/cli 2026.518.2 (latest at the time of writing). CLI
 * updates and reinstalls restore the unpatched bundle, so this is idempotent and
 * re-runnable — start-openacp.ps1 verifies it before every start, the same way it
 * verifies the channel-bindings hook.
 *
 * Usage:
 *   node scripts/patch-openacp-cli.mjs [--cli <path-to-cli.js>] [--check] [--revert]
 */

import { existsSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const ANCHOR = 'const mod = await import(modulePath);';
const PATCHED = 'const mod = await import(pathToFileURL(modulePath).href);';

/**
 * The patch calls pathToFileURL, so the bundle must already import it. It does
 * (importFromDir uses it), but a future bundle might not — and the failure would
 * be a ReferenceError deep inside plugin loading rather than anything obvious.
 */
const REQUIRED_IMPORT = 'import { pathToFileURL } from "url";';

/** CLI release this patch was written against. */
const EXPECTED_CLI_VERSION = '2026.518.2';

function defaultCliPaths() {
  const candidates = [];
  if (process.env.APPDATA) {
    candidates.push(join(process.env.APPDATA, 'npm', 'node_modules', '@openacp', 'cli', 'dist', 'cli.js'));
  }
  const home = process.env.USERPROFILE || process.env.HOME;
  if (home) {
    candidates.push(join(home, '.npm-global', 'lib', 'node_modules', '@openacp', 'cli', 'dist', 'cli.js'));
  }
  candidates.push('/usr/local/lib/node_modules/@openacp/cli/dist/cli.js');
  return candidates.filter((file) => existsSync(file));
}

function cliVersion(file) {
  try {
    return JSON.parse(readFileSync(join(file, '..', '..', 'package.json'), 'utf8')).version || 'unknown';
  } catch {
    return 'unknown';
  }
}

function parseArgs(argv) {
  const args = { check: false, revert: false, clis: [] };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--check') args.check = true;
    else if (argv[i] === '--revert') args.revert = true;
    else if (argv[i] === '--cli') {
      i += 1;
      if (argv[i]) args.clis.push(argv[i]);
    }
  }
  return args;
}

function fail(msg) {
  console.error(`ERROR: ${msg}`);
  process.exit(1);
}

const args = parseArgs(process.argv.slice(2));
const cliFiles = args.clis.length > 0 ? args.clis : defaultCliPaths();

if (cliFiles.length === 0) {
  fail('no installed @openacp/cli found.\nPass an explicit path with --cli <path-to-cli.js>');
}
for (const file of cliFiles) {
  if (!existsSync(file)) fail(`cli.js not found: ${file}`);
}

// ─── --check ────────────────────────────────────────────────────────────────
if (args.check) {
  let allPatched = true;
  for (const file of cliFiles) {
    const patched = readFileSync(file, 'utf8').includes(PATCHED);
    if (!patched) allPatched = false;
    console.log(`${patched ? 'PATCHED      ' : 'NOT PATCHED  '}  ${file}`);
  }
  console.log(allPatched ? 'CLI PATCHED' : 'CLI NOT PATCHED');
  process.exit(allPatched ? 0 : 2);
}

// ─── --revert ───────────────────────────────────────────────────────────────
if (args.revert) {
  for (const file of cliFiles) {
    const original = readFileSync(file, 'utf8');
    if (!original.includes(PATCHED)) {
      console.log(`Nothing to revert in ${file}`);
      continue;
    }
    writeFileSync(file, original.replace(PATCHED, ANCHOR), 'utf8');
    console.log(`Reverted ${file} — npm plugins will not load on Windows again.`);
  }
  process.exit(0);
}

// ─── patch ──────────────────────────────────────────────────────────────────
for (const file of cliFiles) {
  const original = readFileSync(file, 'utf8');

  if (original.includes(PATCHED)) {
    console.log(`Already patched — ${file}`);
    continue;
  }
  if (!original.includes(ANCHOR)) {
    fail(
      `patch anchor not found in ${file}\n` +
        `  installed CLI:    ${cliVersion(file)}\n` +
        `  patch written for: ${EXPECTED_CLI_VERSION}\n` +
        'Either upstream fixed the loader (check for `pathToFileURL(modulePath)` — if it is\n' +
        'there, delete this script and its call in start-openacp.ps1), or the bundle changed\n' +
        'and the anchor needs updating.',
    );
  }
  if (!original.includes(REQUIRED_IMPORT)) {
    fail(
      `${file} does not import pathToFileURL, so this patch would break plugin loading.\n` +
        `  installed CLI:    ${cliVersion(file)}\n` +
        `  patch written for: ${EXPECTED_CLI_VERSION}\n` +
        'Update the patch to import it explicitly before applying.',
    );
  }

  writeFileSync(file, original.replace(ANCHOR, PATCHED), 'utf8');
  console.log(`Patched ${file}`);
}

console.log('\nDone. Restart OpenACP for the change to take effect.');
