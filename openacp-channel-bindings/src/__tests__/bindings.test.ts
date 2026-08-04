import { describe, it, expect, beforeEach } from 'vitest';
import {
  validateChannelBindings,
  resolveBinding,
  loadChannelBindings,
  resetBindingCache,
  TRANSIENT_RETRY_MS,
} from '../bindings.js';
import type { Logger } from '../types.js';

const TEXT_CHANNEL = '111111111111111111';
const FORUM_CHANNEL = '222222222222222222';

const allExist = { workspaceExists: () => true };

describe('validateChannelBindings', () => {
  beforeEach(() => resetBindingCache());

  it('accepts a well-formed config', () => {
    const result = validateChannelBindings(
      {
        [TEXT_CHANNEL]: { agent: 'claude', workspace: 'D:\\Projects\\CrowForge' },
        [FORUM_CHANNEL]: { agent: 'codex', workspace: 'D:\\Projects\\Web' },
      },
      allExist,
    );

    expect(result.issues).toEqual([]);
    expect(result.bindings.size).toBe(2);
    expect(result.bindings.get(TEXT_CHANNEL)).toEqual({
      agent: 'claude',
      workspace: 'D:\\Projects\\CrowForge',
    });
  });

  it('treats a missing config as "no bindings" rather than an error', () => {
    expect(validateChannelBindings(undefined, allExist).bindings.size).toBe(0);
    expect(validateChannelBindings(undefined, allExist).issues).toEqual([]);
    expect(validateChannelBindings(null, allExist).issues).toEqual([]);
  });

  it('rejects a non-object config', () => {
    const result = validateChannelBindings(['nope'], allExist);
    expect(result.bindings.size).toBe(0);
    expect(result.issues[0]?.reason).toMatch(/must be a JSON object/);
  });

  it('rejects malformed entries individually and keeps the valid ones', () => {
    const result = validateChannelBindings(
      {
        'not-a-snowflake': { agent: 'claude', workspace: 'D:\\A' },
        [TEXT_CHANNEL]: { agent: '', workspace: 'D:\\A' },
        [FORUM_CHANNEL]: { agent: 'claude', workspace: 'D:\\Good' },
        '333333333333333333': 'just a string',
        '444444444444444444': { agent: 'claude' },
      },
      allExist,
    );

    expect(result.bindings.size).toBe(1);
    expect(result.bindings.has(FORUM_CHANNEL)).toBe(true);
    expect(result.issues).toHaveLength(4);
    expect(result.invalid.get('not-a-snowflake')).toMatch(/snowflake/);
    expect(result.invalid.get(TEXT_CHANNEL)).toMatch(/"agent" must be/);
    expect(result.invalid.get('444444444444444444')).toMatch(/"workspace" must be/);
  });

  // Requirement 11 + 13: invalid workspace
  it('rejects a binding whose workspace path does not exist', () => {
    const result = validateChannelBindings(
      {
        [TEXT_CHANNEL]: { agent: 'claude', workspace: 'D:\\Does\\Not\\Exist' },
        [FORUM_CHANNEL]: { agent: 'claude', workspace: 'D:\\Real' },
      },
      { workspaceExists: (p) => p === 'D:\\Real' },
    );

    expect(result.bindings.size).toBe(1);
    expect(result.bindings.has(FORUM_CHANNEL)).toBe(true);
    expect(result.invalid.get(TEXT_CHANNEL)).toMatch(/workspace path does not exist/);
  });
});

describe('resolveBinding', () => {
  const validated = validateChannelBindings(
    {
      [TEXT_CHANNEL]: { agent: 'claude', workspace: 'D:\\Real' },
      [FORUM_CHANNEL]: { agent: 'codex', workspace: 'D:\\Nope' },
    },
    { workspaceExists: (p) => p === 'D:\\Real' },
  );

  it('resolves a configured channel', () => {
    const res = resolveBinding(validated, TEXT_CHANNEL);
    expect(res.status).toBe('bound');
    expect(res.status === 'bound' && res.binding.agent).toBe('claude');
  });

  // Requirement 13: unknown channel
  it('reports an unknown channel as unbound', () => {
    expect(resolveBinding(validated, '999999999999999999').status).toBe('unbound');
  });

  it('treats a missing parent channel as unbound', () => {
    expect(resolveBinding(validated, null).status).toBe('unbound');
    expect(resolveBinding(validated, undefined).status).toBe('unbound');
  });

  it('reports a configured-but-invalid channel distinctly from unknown', () => {
    const res = resolveBinding(validated, FORUM_CHANNEL);
    expect(res.status).toBe('invalid');
    expect(res.status === 'invalid' && res.reason).toMatch(/workspace path does not exist/);
  });
});

describe('loadChannelBindings', () => {
  beforeEach(() => resetBindingCache());

  it('memoises against the raw settings object identity', () => {
    let calls = 0;
    const raw = { [TEXT_CHANNEL]: { agent: 'claude', workspace: 'D:\\Real' } };
    const opts = {
      workspaceExists: () => {
        calls += 1;
        return true;
      },
    };

    loadChannelBindings(raw, opts);
    loadChannelBindings(raw, opts);
    expect(calls).toBe(1);

    // A new object (settings.json edited + reloaded) revalidates.
    loadChannelBindings({ ...raw }, opts);
    expect(calls).toBe(2);
  });

  it('keeps memoising indefinitely while nothing is transiently broken', () => {
    let calls = 0;
    const raw = {
      [TEXT_CHANNEL]: { agent: 'claude', workspace: 'D:\\Real' },
      // Structurally broken: no drive coming back can fix this one.
      'not-a-snowflake': { agent: 'claude', workspace: 'D:\\Real' },
    };
    let clock = 0;
    const opts = {
      workspaceExists: () => {
        calls += 1;
        return true;
      },
      now: () => clock,
    };

    loadChannelBindings(raw, opts);
    clock += TRANSIENT_RETRY_MS * 10;
    loadChannelBindings(raw, opts);
    expect(calls).toBe(1);
  });

  // A workspace on a mapped network drive reads as missing until Windows
  // reconnects it. Memoising that verdict on object identity alone froze the
  // binding until OpenACP was restarted.
  it('re-validates a missing workspace once the retry window has passed', () => {
    let connected = false;
    let clock = 0;
    const raw = { [TEXT_CHANNEL]: { agent: 'claude', workspace: 'Z:\\Projects\\Shared' } };
    const opts = {
      workspaceExists: () => connected,
      now: () => clock,
    };

    expect(loadChannelBindings(raw, opts).bindings.size).toBe(0);

    // The drive comes back, but the retry window has not elapsed yet.
    connected = true;
    clock += TRANSIENT_RETRY_MS - 1;
    expect(loadChannelBindings(raw, opts).bindings.size).toBe(0);

    clock += 1;
    const recovered = loadChannelBindings(raw, opts);
    expect(recovered.bindings.size).toBe(1);
    expect(recovered.transient).toBe(false);
    expect(recovered.bindings.get(TEXT_CHANNEL)?.workspace).toBe('Z:\\Projects\\Shared');
  });

  it('logs a repeated transient failure only once', () => {
    const errors: string[] = [];
    const logger: Logger = {
      debug: () => {},
      info: () => {},
      warn: () => {},
      error: (obj: object) => errors.push(JSON.stringify(obj)),
    };
    let clock = 0;
    const raw = { [TEXT_CHANNEL]: { agent: 'claude', workspace: 'Z:\\Gone' } };
    const opts = { workspaceExists: () => false, now: () => clock };

    loadChannelBindings(raw, opts, logger);
    clock += TRANSIENT_RETRY_MS;
    loadChannelBindings(raw, opts, logger);
    clock += TRANSIENT_RETRY_MS;
    loadChannelBindings(raw, opts, logger);

    expect(errors).toHaveLength(1);
  });
});
