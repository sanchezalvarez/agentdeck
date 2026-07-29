import { statSync } from 'node:fs';
import { loadChannelBindings, resolveBinding, type ValidateOptions } from './bindings.js';
import { ensureSessionForThread, type CoreLike } from './session-link.js';
import { LOG_PREFIX, type Logger } from './types.js';

/** Real filesystem check used in production (requirement: validate workspaces). */
export function workspaceExists(path: string): boolean {
  try {
    return statSync(path).isDirectory();
  } catch {
    return false;
  }
}

/** Duck-typed DiscordAdapter — only the fields the hook reads. */
export interface AdapterLike {
  core: CoreLike;
  discordConfig: {
    channelBindings?: unknown;
    assistantThreadId?: string | null;
    [key: string]: unknown;
  };
}

/** Duck-typed discord.js Message. */
export interface MessageLike {
  channel: {
    id: string;
    parentId?: string | null;
  };
}

export interface HookDeps {
  workspaceExists?: (path: string) => boolean;
}

/**
 * Entry point called from the adapter's messageCreate handler.
 *
 * Returns the session ID to use for this message, or null to leave the
 * adapter's existing behaviour untouched (message outside a configured
 * project channel, assistant thread, broken binding, or creation failure).
 */
export async function ensureBoundSession(
  adapter: AdapterLike,
  message: MessageLike,
  logger?: Logger,
  deps: HookDeps = {},
): Promise<string | null> {
  const threadId = message.channel.id;
  const parentChannelId = message.channel.parentId ?? null;

  // The assistant thread owns its own session lifecycle — never touch it.
  const assistantThreadId = adapter.discordConfig.assistantThreadId;
  if (assistantThreadId && threadId === assistantThreadId) return null;

  // No parent channel means this is not a thread inside a project channel.
  if (!parentChannelId) {
    logger?.debug({ threadId }, `${LOG_PREFIX} Message has no parent channel — ignoring`);
    return null;
  }

  const validateOpts: ValidateOptions = {
    workspaceExists: deps.workspaceExists ?? workspaceExists,
  };
  const validated = loadChannelBindings(
    adapter.discordConfig.channelBindings,
    validateOpts,
    logger,
  );

  // Nothing configured — behave exactly like the unmodified adapter.
  if (validated.bindings.size === 0 && validated.invalid.size === 0) return null;

  const resolution = resolveBinding(validated, parentChannelId);

  if (resolution.status === 'unbound') {
    logger?.debug(
      { threadId, parentChannelId },
      `${LOG_PREFIX} Thread is not inside a configured project channel — ignoring`,
    );
    return null;
  }

  if (resolution.status === 'invalid') {
    logger?.error(
      { threadId, parentChannelId, reason: resolution.reason },
      `${LOG_PREFIX} Message arrived in a channel with an invalid binding — ignoring`,
    );
    return null;
  }

  const { binding } = resolution;
  logger?.debug(
    { threadId, parentChannelId, agent: binding.agent, workspace: binding.workspace },
    `${LOG_PREFIX} Binding resolved`,
  );

  const link = await ensureSessionForThread({
    core: adapter.core,
    threadId,
    parentChannelId,
    binding,
    logger,
  });

  return link?.sessionId ?? null;
}
