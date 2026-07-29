import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    // Only this module's own tests. The backup/ folder holds a verbatim copy of
    // the adapter's shipped dist (including its compiled test files), which
    // cannot resolve discord.js / @openacp/plugin-sdk from here.
    include: ['src/**/*.test.ts'],
    exclude: ['node_modules/**', 'dist/**', 'backup/**'],
  },
});
