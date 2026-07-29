/**
 * Shared types for the channel-binding feature.
 *
 * Nothing here depends on discord.js or @openacp/plugin-sdk — the runtime
 * objects are duck-typed so the whole module stays unit-testable without a
 * live Discord client or a running OpenACP kernel.
 */

/** A project binding: one Discord channel -> one fixed agent + workspace. */
export interface ChannelBinding {
  agent: string;
  workspace: string;
}

/**
 * Pino-style logger, matching the `log` export of @openacp/plugin-sdk that
 * the adapter already uses. The hook passes the adapter's own logger in, so
 * binding logs land in the same stream as the rest of the adapter.
 */
export interface Logger {
  debug(obj: object, msg?: string): void;
  info(obj: object, msg?: string): void;
  warn(obj: object, msg?: string): void;
  error(obj: object, msg?: string): void;
}

export const LOG_PREFIX = '[discord-bindings]';
