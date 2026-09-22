import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

describe('LandingPage hero copy', () => {
  it('uses the updated headline text', () => {
    const currentDir = dirname(fileURLToPath(import.meta.url));
    const source = readFileSync(resolve(currentDir, '../src/pages/LandingPage.tsx'), 'utf-8');

    expect(source).toContain('Imagine. Create. Build.');
    expect(source).not.toContain('Imagine. Customize. Build.');
  });
});
