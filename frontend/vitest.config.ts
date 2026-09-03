import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json-summary'],
      include: ['src/services/**/*.ts', 'src/utils/**/*.ts'],
      thresholds: { lines: 70, functions: 70, statements: 70, branches: 50 },
    },
  },
});
