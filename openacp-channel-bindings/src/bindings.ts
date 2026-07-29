import { LOG_PREFIX, type ChannelBinding, type Logger } from './types.js';

/** Discord snowflakes are 17-20 digit numeric strings. */
const SNOWFLAKE = /^\d{17,20}$/;

export interface ValidationIssue {
  channelId: string;
  reason: string;
}

export interface ValidatedBindings {
  /** Channels that passed every check and are safe to route to. */
  bindings: Map<string, ChannelBinding>;
  /**
   * Channels that were configured but rejected, keyed by channel ID.
   * Kept separately so an incoming message in a broken channel can be
   * reported with the concrete reason instead of silently ignored.
   */
  invalid: Map<string, string>;
  issues: ValidationIssue[];
}

export interface ValidateOptions {
  /** Injected so tests never touch the real filesystem. */
  workspaceExists?: (path: string) => boolean;
}

/**
 * Validates the raw `channelBindings` value from plugin settings.
 *
 * Invalid entries are dropped individually rather than failing the whole
 * config — one typo must not disable every other project channel.
 */
export function validateChannelBindings(
  raw: unknown,
  opts: ValidateOptions = {},
): ValidatedBindings {
  const workspaceExists = opts.workspaceExists ?? (() => true);
  const bindings = new Map<string, ChannelBinding>();
  const invalid = new Map<string, string>();
  const issues: ValidationIssue[] = [];

  const reject = (channelId: string, reason: string): void => {
    invalid.set(channelId, reason);
    issues.push({ channelId, reason });
  };

  if (raw === undefined || raw === null) {
    return { bindings, invalid, issues };
  }

  if (typeof raw !== 'object' || Array.isArray(raw)) {
    reject('<root>', 'channelBindings must be a JSON object');
    return { bindings, invalid, issues };
  }

  for (const [channelId, value] of Object.entries(raw as Record<string, unknown>)) {
    if (!SNOWFLAKE.test(channelId)) {
      reject(channelId, 'channel ID must be a numeric Discord snowflake (17-20 digits)');
      continue;
    }
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      reject(channelId, 'binding must be an object with "agent" and "workspace"');
      continue;
    }

    const { agent, workspace } = value as Record<string, unknown>;

    if (typeof agent !== 'string' || agent.trim() === '') {
      reject(channelId, '"agent" must be a non-empty string');
      continue;
    }
    if (typeof workspace !== 'string' || workspace.trim() === '') {
      reject(channelId, '"workspace" must be a non-empty string');
      continue;
    }
    if (!workspaceExists(workspace)) {
      reject(channelId, `workspace path does not exist: ${workspace}`);
      continue;
    }

    bindings.set(channelId, { agent: agent.trim(), workspace });
  }

  return { bindings, invalid, issues };
}

export type Resolution =
  | { status: 'bound'; binding: ChannelBinding }
  | { status: 'unbound' }
  | { status: 'invalid'; reason: string };

/**
 * Maps a thread's parent channel ID onto a configured binding.
 *
 * The parent of a thread in a text channel and the parent of a post inside a
 * forum channel are both plain channel IDs, so text and forum channels need
 * no separate handling here.
 */
export function resolveBinding(
  validated: ValidatedBindings,
  parentChannelId: string | null | undefined,
): Resolution {
  if (!parentChannelId) return { status: 'unbound' };

  const binding = validated.bindings.get(parentChannelId);
  if (binding) return { status: 'bound', binding };

  const reason = validated.invalid.get(parentChannelId);
  if (reason) return { status: 'invalid', reason };

  return { status: 'unbound' };
}

// ─── cached loading ─────────────────────────────────────────────────────────
// Settings are re-read on every message; validating (and stat-ing workspace
// paths) each time would be wasteful, so the result is memoised against the
// identity of the raw settings object. Editing settings.json produces a new
// object, which invalidates the cache naturally.

let cacheKey: unknown = Symbol('empty');
let cacheValue: ValidatedBindings | null = null;

export function loadChannelBindings(
  raw: unknown,
  opts: ValidateOptions = {},
  logger?: Logger,
): ValidatedBindings {
  if (cacheValue !== null && cacheKey === raw) return cacheValue;

  const result = validateChannelBindings(raw, opts);

  for (const issue of result.issues) {
    logger?.error(
      { channelId: issue.channelId, reason: issue.reason },
      `${LOG_PREFIX} Invalid channel binding — entry ignored`,
    );
  }
  if (result.bindings.size > 0) {
    logger?.info(
      { count: result.bindings.size, channels: [...result.bindings.keys()] },
      `${LOG_PREFIX} Channel bindings loaded`,
    );
  }

  cacheKey = raw;
  cacheValue = result;
  return result;
}

/** Test seam — drops the memoised validation result. */
export function resetBindingCache(): void {
  cacheKey = Symbol('empty');
  cacheValue = null;
}
