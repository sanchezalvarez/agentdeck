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

/**
 * Every place the bundle imports a plugin by absolute path. Fixing only the boot
 * loader is not enough: the onboarding wizard hits the same bug when it sets up
 * Discord, and its catch block then registers the adapter as `enabled: false`
 * with version "unknown" *and* skips the plugin's install hook — which is the
 * step that asks for the bot token. So onboarding appears to succeed while
 * leaving Discord unconfigured and switched off.
 *
 * `expected` guards against a bundle that changes how many times a site appears:
 * a silent 1-of-2 replacement would leave a working CLI that still breaks in one
 * path, which is far harder to notice than a hard failure here.
 */
const PATCHES = [
  {
    what: 'community plugin boot loader',
    anchor: 'const mod = await import(modulePath);',
    patched: 'const mod = await import(pathToFileURL(modulePath).href);',
    expected: 1,
  },
  {
    what: 'onboarding wizard (official + community adapters)',
    anchor: 'await import(path53.join(nodeModulesDir, npmPackage, installedPkg.main ?? "dist/index.js"))',
    patched:
      'await import(pathToFileURL(path53.join(nodeModulesDir, npmPackage, installedPkg.main ?? "dist/index.js")).href)',
    expected: 2,
  },
  {
    what: 'openacp install / plugin add',
    anchor: 'await import(path71.join(pluginRoot, installedPkg.main ?? "dist/index.js"))',
    patched: 'await import(pathToFileURL(path71.join(pluginRoot, installedPkg.main ?? "dist/index.js")).href)',
    expected: 1,
  },
];

/**
 * The patch calls pathToFileURL, so the bundle must already import it. It does
 * (importFromDir uses it), but a future bundle might not — and the failure would
 * be a ReferenceError deep inside plugin loading rather than anything obvious.
 */
const REQUIRED_IMPORT = 'import { pathToFileURL } from "url";';

function countOf(haystack, needle) {
  let count = 0;
  let at = haystack.indexOf(needle);
  while (at !== -1) {
    count += 1;
    at = haystack.indexOf(needle, at + needle.length);
  }
  return count;
}

/** Patched when every site is done; unpatched only when none is. */
function patchState(source) {
  const done = PATCHES.filter((p) => countOf(source, p.patched) === p.expected);
  return { done: done.length, total: PATCHES.length, complete: done.length === PATCHES.length };
}

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
    const state = patchState(readFileSync(file, 'utf8'));
    if (!state.complete) allPatched = false;
    console.log(
      `${state.complete ? 'PATCHED      ' : 'NOT PATCHED  '}  ${state.done}/${state.total} sites  ${file}`,
    );
  }
  console.log(allPatched ? 'CLI PATCHED' : 'CLI NOT PATCHED');
  process.exit(allPatched ? 0 : 2);
}

// ─── --revert ───────────────────────────────────────────────────────────────
if (args.revert) {
  for (const file of cliFiles) {
    const original = readFileSync(file, 'utf8');
    let source = original;
    for (const p of PATCHES) source = source.split(p.patched).join(p.anchor);

    if (source === original) {
      console.log(`Nothing to revert in ${file}`);
      continue;
    }
    writeFileSync(file, source, 'utf8');
    console.log(`Reverted ${file} — npm plugins will not load on Windows again.`);
  }
  process.exit(0);
}

// ─── patch ──────────────────────────────────────────────────────────────────
for (const file of cliFiles) {
  const original = readFileSync(file, 'utf8');
  const state = patchState(original);

  if (state.complete) {
    console.log(`Already patched (${state.done}/${state.total} sites) — ${file}`);
    continue;
  }
  if (!original.includes(REQUIRED_IMPORT)) {
    fail(
      `${file} does not import pathToFileURL, so this patch would break plugin loading.\n` +
        `  installed CLI:    ${cliVersion(file)}\n` +
        `  patch written for: ${EXPECTED_CLI_VERSION}\n` +
        'Update the patch to import it explicitly before applying.',
    );
  }

  let source = original;
  for (const p of PATCHES) {
    const alreadyDone = countOf(source, p.patched);
    if (alreadyDone === p.expected) continue;

    const found = countOf(source, p.anchor);
    if (found !== p.expected) {
      fail(
        `expected ${p.expected} occurrence(s) of the ${p.what} anchor in ${file}, found ${found}\n` +
          `  installed CLI:    ${cliVersion(file)}\n` +
          `  patch written for: ${EXPECTED_CLI_VERSION}\n` +
          'Either upstream fixed these imports (check for `pathToFileURL` around them — if they\n' +
          'are fixed, drop that entry from PATCHES, or delete this script and its call in\n' +
          'start-openacp.ps1 once none are left), or the bundle changed and the anchor needs\n' +
          'updating. Nothing has been written.',
      );
    }
    source = source.split(p.anchor).join(p.patched);
  }

  writeFileSync(file, source, 'utf8');
  console.log(`Patched ${patchState(source).done}/${PATCHES.length} sites in ${file}`);
}

console.log('\nDone. Restart OpenACP for the change to take effect.');
