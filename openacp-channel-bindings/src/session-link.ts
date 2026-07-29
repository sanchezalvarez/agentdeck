import { LOG_PREFIX, type ChannelBinding, type Logger } from './types.js';

/**
 * Minimal shape of an OpenACP session record, as returned by
 * `core.handleNewSession()` and `sessionManager.getSessionByThread()`.
 */
export interface SessionRecordLike {
  id: string;
  agentName?: string;
  workingDirectory?: string;
  threadId?: string;
}

/**
 * The exact subset of OpenACPCore this module touches. Both calls are the
 * ones the existing `/new` command uses (see commands/new-session.js), so
 * bound-channel sessions travel the same code path as manual ones.
 */
export interface CoreLike {
  handleNewSession(
    channelId: string,
    agent: string,
    workspace: string,
  ): Promise<SessionRecordLike>;
  sessionManager: {
    getSessionByThread(
      channelId: string,
      threadId: string,
    ): SessionRecordLike | null | undefined;
    patchRecord(sessionId: string, patch: Record<string, unknown>): Promise<void>;
  };
}

export interface LinkResult {
  sessionId: string;
  /** false when an existing session was resumed. */
  created: boolean;
}

/**
 * Guards against the race where a user posts two messages into a brand-new
 * thread faster than the first session finishes spawning. Without this, both
 * messages would see "no session" and create one each.
 */
const inFlight = new Map<string, Promise<LinkResult | null>>();

export interface EnsureSessionArgs {
  core: CoreLike;
  threadId: string;
  parentChannelId: string;
  binding: ChannelBinding;
  logger?: Logger;
}

/**
 * Returns the OpenACP session bound to `threadId`, creating one from the
 * channel binding if this is the thread's first message.
 *
 * Returns null if session creation failed — the caller then falls back to the
 * adapter's normal "unknown session" behaviour instead of crashing the
 * messageCreate handler.
 */
export async function ensureSessionForThread(
  args: EnsureSessionArgs,
): Promise<LinkResult | null> {
  const { core, threadId, parentChannelId, binding, logger } = args;

  const existing = core.sessionManager.getSessionByThread('discord', threadId);
  if (existing?.id) {
    logger?.info(
      { threadId, parentChannelId, sessionId: existing.id, agent: binding.agent },
      `${LOG_PREFIX} Existing session resumed`,
    );
    return { sessionId: existing.id, created: false };
  }

  const pending = inFlight.get(threadId);
  if (pending) return pending;

  const task = (async (): Promise<LinkResult | null> => {
    try {
      // Same creation path as /new — only the thread already exists here,
      // because Discord created it when the user opened the thread/post.
      const session = await core.handleNewSession('discord', binding.agent, binding.workspace);
      session.threadId = threadId;

      // Persists thread -> session mapping (plus agent, workspace and the
      // owning project channel) into the session store, so the link survives
      // an OpenACP restart and getSessionByThread finds it again.
      await core.sessionManager.patchRecord(session.id, {
        platform: { threadId, parentChannelId },
      });

      logger?.info(
        {
          threadId,
          parentChannelId,
          sessionId: session.id,
          agent: binding.agent,
          workspace: binding.workspace,
        },
        `${LOG_PREFIX} Session created for bound project thread`,
      );
      return { sessionId: session.id, created: true };
    } catch (err) {
      logger?.error(
        { err, threadId, parentChannelId, agent: binding.agent, workspace: binding.workspace },
        `${LOG_PREFIX} Failed to create session for bound project thread`,
      );
      return null;
    }
  })();

  inFlight.set(threadId, task);
  try {
    return await task;
  } finally {
    inFlight.delete(threadId);
  }
}

/** Test seam — clears pending in-flight creations. */
export function resetInFlight(): void {
  inFlight.clear();
}
