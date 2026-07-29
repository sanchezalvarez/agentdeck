import { describe, it, expect, beforeEach } from 'vitest';
import { ensureBoundSession, type AdapterLike, type MessageLike } from '../adapter-hook.js';
import { resetBindingCache } from '../bindings.js';
import { resetInFlight } from '../session-link.js';
import { FakeCore, SessionStore, makeLogger } from './fake-core.js';

const TEXT_CHANNEL = '111111111111111111';
const FORUM_CHANNEL = '222222222222222222';
const UNBOUND_CHANNEL = '999999999999999999';
const BROKEN_CHANNEL = '333333333333333333';
const ASSISTANT_THREAD = '888888888888888888';

const CROWFORGE = 'D:\\Projects\\CrowForge';
const WEB = 'D:\\Projects\\Web';
const MISSING = 'D:\\Projects\\Gone';

const CHANNEL_BINDINGS = {
  [TEXT_CHANNEL]: { agent: 'claude', workspace: CROWFORGE },
  [FORUM_CHANNEL]: { agent: 'codex', workspace: WEB },
  [BROKEN_CHANNEL]: { agent: 'claude', workspace: MISSING },
};

/** Only the two real project paths exist on this fake filesystem. */
const fakeFs = { workspaceExists: (p: string) => p === CROWFORGE || p === WEB };

function makeAdapter(core: FakeCore): AdapterLike {
  return {
    core,
    discordConfig: {
      channelBindings: CHANNEL_BINDINGS,
      assistantThreadId: ASSISTANT_THREAD,
    },
  };
}

function message(threadId: string, parentId: string | null): MessageLike {
  return { channel: { id: threadId, parentId } };
}

describe('ensureBoundSession', () => {
  let store: SessionStore;
  let core: FakeCore;
  let adapter: AdapterLike;

  beforeEach(() => {
    resetBindingCache();
    resetInFlight();
    store = new SessionStore();
    core = new FakeCore(store);
    adapter = makeAdapter(core);
  });

  // Requirement 13: text channel thread binding + automatic session creation
  it('creates a session for a thread under a bound text channel', async () => {
    const { logger, logged } = makeLogger();

    const sessionId = await ensureBoundSession(
      adapter,
      message('T1', TEXT_CHANNEL),
      logger,
      fakeFs,
    );

    expect(sessionId).toBe('S1');
    expect(core.handleNewSessionCalls).toEqual([
      { channelId: 'discord', agent: 'claude', workspace: CROWFORGE },
    ]);
    expect(logged('Binding resolved')).toBe(true);
    expect(logged('Session created')).toBe(true);
  });

  // Requirement 13: forum thread binding
  it('creates a session for a post inside a bound forum channel', async () => {
    const sessionId = await ensureBoundSession(
      adapter,
      message('F1', FORUM_CHANNEL),
      undefined,
      fakeFs,
    );

    expect(sessionId).toBe('S1');
    // The forum channel is bound to a different agent and workspace.
    expect(core.handleNewSessionCalls).toEqual([
      { channelId: 'discord', agent: 'codex', workspace: WEB },
    ]);
  });

  it('keeps separate sessions for separate threads in the same channel', async () => {
    const a = await ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), undefined, fakeFs);
    const b = await ensureBoundSession(adapter, message('T2', TEXT_CHANNEL), undefined, fakeFs);

    expect(a).toBe('S1');
    expect(b).toBe('S2');
    expect(core.handleNewSessionCalls).toHaveLength(2);
  });

  // Requirement 13: session reuse
  it('reuses the existing session for follow-up messages in the same thread', async () => {
    const first = await ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), undefined, fakeFs);

    const { logger, logged } = makeLogger();
    const second = await ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), logger, fakeFs);
    const third = await ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), logger, fakeFs);

    expect(second).toBe(first);
    expect(third).toBe(first);
    expect(core.handleNewSessionCalls).toHaveLength(1);
    expect(logged('Existing session resumed')).toBe(true);
  });

  it('does not create two sessions when messages race in a new thread', async () => {
    const [a, b] = await Promise.all([
      ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), undefined, fakeFs),
      ensureBoundSession(adapter, message('T1', TEXT_CHANNEL), undefined, fakeFs),
    ]);

    expect(a).toBe('S1');
    expect(b).toBe('S1');
    expect(core.handleNewSessionCalls).toHaveLength(1);
  });

  // Requirement 13: persistence after restart
  it('restores the thread -> session mapping after an OpenACP restart', async () => {
    const before = await ensureBoundSession(
      adapter,
      message('T1', TEXT_CHANNEL),
      undefined,
      fakeFs,
    );
    expect(before).toBe('S1');

    // The mapping must live in the persisted store, not in adapter memory.
    const persisted = store.sessions.find((s) => s.sessionId === 'S1');
    expect(persisted?.platform).toMatchObject({
      threadId: 'T1',
      parentChannelId: TEXT_CHANNEL,
    });
    expect(persisted?.agentName).toBe('claude');
    expect(persisted?.workingDir).toBe(CROWFORGE);

    // Simulate restart: fresh core + fresh caches over the same store.
    resetBindingCache();
    resetInFlight();
    const restartedCore = new FakeCore(store);
    const restartedAdapter = makeAdapter(restartedCore);

    const after = await ensureBoundSession(
      restartedAdapter,
      message('T1', TEXT_CHANNEL),
      undefined,
      fakeFs,
    );

    expect(after).toBe('S1');
    expect(restartedCore.handleNewSessionCalls).toHaveLength(0);
  });

  // Requirement 13: unknown channel (requirement 8: ignore)
  it('ignores threads under an unconfigured channel', async () => {
    const sessionId = await ensureBoundSession(
      adapter,
      message('X1', UNBOUND_CHANNEL),
      undefined,
      fakeFs,
    );

    expect(sessionId).toBeNull();
    expect(core.handleNewSessionCalls).toHaveLength(0);
  });

  it('ignores top-level messages that have no parent channel', async () => {
    const sessionId = await ensureBoundSession(adapter, message('X1', null), undefined, fakeFs);
    expect(sessionId).toBeNull();
    expect(core.handleNewSessionCalls).toHaveLength(0);
  });

  // Requirement 13: invalid workspace
  it('refuses to start a session when the configured workspace is missing', async () => {
    const { logger, logged, entries } = makeLogger();

    const sessionId = await ensureBoundSession(
      adapter,
      message('B1', BROKEN_CHANNEL),
      logger,
      fakeFs,
    );

    expect(sessionId).toBeNull();
    expect(core.handleNewSessionCalls).toHaveLength(0);
    expect(logged('Invalid channel binding')).toBe(true);
    expect(entries.some((e) => e.level === 'error')).toBe(true);
  });

  it('never hijacks the assistant thread', async () => {
    const adapterWithBoundAssistant: AdapterLike = {
      core,
      discordConfig: {
        channelBindings: CHANNEL_BINDINGS,
        assistantThreadId: ASSISTANT_THREAD,
      },
    };

    const sessionId = await ensureBoundSession(
      adapterWithBoundAssistant,
      message(ASSISTANT_THREAD, TEXT_CHANNEL),
      undefined,
      fakeFs,
    );

    expect(sessionId).toBeNull();
    expect(core.handleNewSessionCalls).toHaveLength(0);
  });

  // Requirement 9: unchanged behaviour when the feature is not configured
  it('stays inert when no channelBindings are configured', async () => {
    const plain: AdapterLike = { core, discordConfig: { assistantThreadId: null } };

    const sessionId = await ensureBoundSession(
      plain,
      message('T1', TEXT_CHANNEL),
      undefined,
      fakeFs,
    );

    expect(sessionId).toBeNull();
    expect(core.handleNewSessionCalls).toHaveLength(0);
  });

  it('falls back to null when session creation fails', async () => {
    const failingCore = new FakeCore(store, { failCreation: true });
    const { logger, logged } = makeLogger();

    const sessionId = await ensureBoundSession(
      makeAdapter(failingCore),
      message('T1', TEXT_CHANNEL),
      logger,
      fakeFs,
    );

    expect(sessionId).toBeNull();
    expect(logged('Failed to create session')).toBe(true);
  });
});
