import type { CoreLike, SessionRecordLike } from '../session-link.js';

/**
 * Stand-in for the persisted session store (.openacp/sessions.json).
 * Shared across FakeCore instances so a "restart" can be simulated by
 * building a fresh core over the same store.
 */
export interface StoredSession {
  sessionId: string;
  agentName: string;
  workingDir: string;
  channelId: string;
  platform: Record<string, unknown>;
}

export class SessionStore {
  sessions: StoredSession[] = [];
}

export class FakeCore implements CoreLike {
  handleNewSessionCalls: Array<{ channelId: string; agent: string; workspace: string }> = [];
  private seq = 0;

  constructor(
    private store: SessionStore,
    private opts: { failCreation?: boolean } = {},
  ) {}

  async handleNewSession(
    channelId: string,
    agent: string,
    workspace: string,
  ): Promise<SessionRecordLike> {
    this.handleNewSessionCalls.push({ channelId, agent, workspace });
    if (this.opts.failCreation) throw new Error('agent spawn failed');

    this.seq += 1;
    const sessionId = `S${this.seq}`;
    this.store.sessions.push({
      sessionId,
      agentName: agent,
      workingDir: workspace,
      channelId,
      platform: {},
    });
    return { id: sessionId, agentName: agent, workingDirectory: workspace };
  }

  sessionManager = {
    getSessionByThread: (channelId: string, threadId: string): SessionRecordLike | null => {
      const rec = this.store.sessions.find(
        (s) => s.channelId === channelId && s.platform['threadId'] === threadId,
      );
      if (!rec) return null;
      return {
        id: rec.sessionId,
        agentName: rec.agentName,
        workingDirectory: rec.workingDir,
        threadId: String(rec.platform['threadId']),
      };
    },

    patchRecord: async (sessionId: string, patch: Record<string, unknown>): Promise<void> => {
      const rec = this.store.sessions.find((s) => s.sessionId === sessionId);
      if (!rec) throw new Error(`unknown session ${sessionId}`);
      const platformPatch = patch['platform'];
      if (platformPatch && typeof platformPatch === 'object') {
        rec.platform = { ...rec.platform, ...(platformPatch as Record<string, unknown>) };
      }
    },
  };
}

/** Collects log calls so tests can assert on the required log events. */
export function makeLogger() {
  const entries: Array<{ level: string; obj: object; msg?: string }> = [];
  const push = (level: string) => (obj: object, msg?: string) => {
    entries.push({ level, obj, msg });
  };
  return {
    entries,
    logger: {
      debug: push('debug'),
      info: push('info'),
      warn: push('warn'),
      error: push('error'),
    },
    /** True if any message contains the given fragment. */
    logged(fragment: string): boolean {
      return entries.some((e) => (e.msg ?? '').includes(fragment));
    },
  };
}
