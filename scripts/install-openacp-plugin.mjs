#!/usr/bin/env node
/**
 * Installs @openacp/discord-adapter as an OpenACP *workspace* plugin.
 *
 * OpenACP loads adapters from ~/openacp-workspace/.openacp/plugins/node_modules and
 * boots only what .openacp/plugins.json lists. A global `npm install -g` — which is
 * all the dashboard's "Install OpenACP" button does — satisfies neither, so Discord
 * stays completely silent while every obvious check still looks healthy: the package
 * is in `npm ls -g`, settings.json exists, and the channel-bindings hook reports
 * INSTALLED because it patched the global copy nobody loads.
 *
 * Both supported ways to fix that are broken on Windows in @openacp/cli 2026.518.2:
 *
 *   openacp install <pkg>   ->  execFileSync("npm", ...)   (same code path as
 *   openacp plugin add <pkg>                                `openacp plugin add`)
 *   the onboarding wizard   ->  execFileAsync("npm", ...) via installNpmPlugin()
 *
 * execFile without shell:true cannot run npm.cmd, so both fail with ENOENT, which
 * the CLI reports as the misleading "Failed to install ... Check the package name
 * and try again". This script does the same two steps correctly: npm install into
 * the plugins directory, then the plugins.json registry entry the CLI would have
 * written.
 *
 * It deliberately does NOT run the plugin's interactive install hook — that
 * rewrites settings.json and would destroy the bot token and every channel binding
 * on an already-configured PC. A fresh PC has no settings.json yet; configure the
 * bot afterwards (see AGENTS.md "Moving to another PC").
 *
 * Idempotent and re-runnable. start-openacp.ps1 checks it before every start.
 *
 * Usage:
 *   node scripts/install-openacp-plugin.mjs [--check] [--workspace <dir>]
 */

import { spawnSync } from 'node:child_process';
import { existsSync as exists, mkdirSync as mkdir, readFileSync as read, writeFileSync as write } from 'node:fs';
import { dirname, join } from 'node:path';

const PACKAGE = '@openacp/discord-adapter';

/**
 * Kept in sync manually with backend/app/services/openacp_install.py (ADAPTER_VERSION)
 * and scripts/diagnose-new-pc.ps1 ($PinnedAdapterVersion) — bump all three together.
 * The version is pinned because openacp-channel-bindings patches the adapter's
 * compiled dist by matching exact code anchors.
 */
const PINNED_VERSION = '2026.518.1';

function parseArgs(argv) {
  const args = { check: false, workspace: null };
  for (let i = 0; i < argv.length; i += 1) {
    if (argv[i] === '--check') args.check = true;
    else if (argv[i] === '--workspace') {
      i += 1;
      if (argv[i]) args.workspace = argv[i];
    }
  }
  return args;
}

function fail(msg) {
  console.error(`ERROR: ${msg}`);
  process.exit(1);
}

const args = parseArgs(process.argv.slice(2));

const home = process.env.USERPROFILE || process.env.HOME;
const workspace = args.workspace || process.env.OPENACP_WORKSPACE || (home ? join(home, 'openacp-workspace') : null);
if (!workspace) fail('cannot determine the OpenACP workspace — pass --workspace <dir>');

const root = join(workspace, '.openacp');
const pluginsDir = join(root, 'plugins');
const registryPath = join(root, 'plugins.json');
const adapterDir = join(pluginsDir, 'node_modules', '@openacp', 'discord-adapter');

/** The dist is what OpenACP actually imports; an entry without it is not installed. */
function adapterInstalled() {
  return exists(join(adapterDir, 'dist', 'index.js'));
}

function registryHasAdapter() {
  if (!exists(registryPath)) return false;
  try {
    return Boolean(JSON.parse(read(registryPath, 'utf8'))?.installed?.[PACKAGE]);
  } catch {
    return false;
  }
}

// ─── --check ────────────────────────────────────────────────────────────────
if (args.check) {
  const installed = adapterInstalled();
  const registered = registryHasAdapter();
  console.log(`${installed ? 'INSTALLED    ' : 'MISSING      '}  workspace plugin  ${adapterDir}`);
  console.log(`${registered ? 'REGISTERED   ' : 'MISSING      '}  registry entry    ${registryPath}`);
  const ok = installed && registered;
  console.log(ok ? 'WORKSPACE PLUGIN READY' : 'WORKSPACE PLUGIN NOT READY');
  process.exit(ok ? 0 : 2);
}

// ─── install ────────────────────────────────────────────────────────────────
if (!exists(root)) {
  fail(
    `${root} does not exist — OpenACP has never initialised this workspace.\n` +
      'Run scripts\\start-openacp.ps1 once and let it bootstrap .openacp\\, then run this again.',
  );
}

if (!exists(pluginsDir)) mkdir(pluginsDir, { recursive: true });

// A plugins/package.json must exist for `npm install --save` to record the
// dependency; OpenACP ships one, but a hand-made workspace may not have it.
const manifestPath = join(pluginsDir, 'package.json');
if (!exists(manifestPath)) {
  write(manifestPath, `${JSON.stringify({ name: 'openacp-plugins', private: true, dependencies: {} }, null, 2)}\n`, 'utf8');
  console.log(`Created ${manifestPath}`);
}

/**
 * Runs `npm install` without tripping over how Windows executes npm.
 *
 * Spawning the bare name is what breaks inside the OpenACP CLI (execFile("npm")
 * cannot find npm.cmd), but naming npm.cmd explicitly is not the fix either:
 * since CVE-2024-27980, Node refuses to spawn a .cmd without shell:true and
 * throws EINVAL. So invoke npm's JS entry point with the Node already running —
 * no shell, no quoting, nothing platform-specific. This is the same approach the
 * OpenACP CLI itself uses to resolve npx.
 */
function runNpmInstall(spec, cwd) {
  const options = { cwd, stdio: 'inherit', timeout: 300000 };
  const npmCli = join(dirname(process.execPath), 'node_modules', 'npm', 'bin', 'npm-cli.js');

  if (exists(npmCli)) {
    return spawnSync(process.execPath, [npmCli, 'install', spec, '--save'], options);
  }
  // Node installed without its bundled npm — let the shell resolve npm instead.
  return spawnSync('npm', ['install', spec, '--save'], { ...options, shell: true });
}

if (adapterInstalled()) {
  console.log(`Already installed — ${adapterDir}`);
} else {
  const spec = `${PACKAGE}@${PINNED_VERSION}`;
  console.log(`Installing ${spec} into ${pluginsDir} ...`);

  const result = runNpmInstall(spec, pluginsDir);

  if (result.error) fail(`could not run npm: ${result.error.message}`);
  if (result.status !== 0) fail(`npm install failed with exit code ${result.status}`);
  if (!adapterInstalled()) fail(`npm reported success but ${adapterDir}\\dist is still missing`);
  console.log(`Installed ${spec}`);
}

// ─── registry entry ─────────────────────────────────────────────────────────
// npm alone does not register the plugin, and OpenACP boots only what plugins.json
// lists — an installed-but-unregistered adapter is silently never loaded.
if (registryHasAdapter()) {
  console.log(`Already registered in ${registryPath}`);
} else {
  let registry = { installed: {} };
  if (exists(registryPath)) {
    try {
      registry = JSON.parse(read(registryPath, 'utf8'));
    } catch (err) {
      fail(`${registryPath} is not valid JSON (${err.message}) — fix or delete it, then run this again.`);
    }
  }
  if (!registry.installed) registry.installed = {};

  let version = PINNED_VERSION;
  let description = 'Discord adapter plugin for OpenACP';
  try {
    const pkg = JSON.parse(read(join(adapterDir, 'package.json'), 'utf8'));
    version = pkg.version || version;
    description = pkg.description || description;
  } catch {
    // Fall back to the pinned values; the entry matters more than its metadata.
  }

  const now = new Date().toISOString();
  registry.installed[PACKAGE] = {
    version,
    source: 'npm',
    enabled: true,
    settingsPath: join(pluginsDir, 'data', '@openacp', 'discord-adapter', 'settings.json'),
    description,
    installedAt: now,
    updatedAt: now,
  };

  write(registryPath, `${JSON.stringify(registry, null, 2)}\n`, 'utf8');
  console.log(`Registered ${PACKAGE} in ${registryPath}`);
}

console.log('\nDone. Restart OpenACP for the change to take effect.');
