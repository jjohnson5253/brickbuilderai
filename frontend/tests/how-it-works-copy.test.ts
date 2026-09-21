import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('landing page how it works copy', () => {
  it('includes a child-friendly GitHub learn-more message', () => {
    const landingPagePath = resolve(
      process.cwd(),
      'src/pages/LandingPage.tsx',
    );
    const landingPageSource = readFileSync(landingPagePath, 'utf8');

    expect(landingPageSource).toContain('Want to learn the magic?');
    expect(landingPageSource).toContain(
      'try running it yourself by exploring the code on',
    );
    expect(landingPageSource).toContain(
      'https://github.com/jjohnson5253/brickbuilderai',
    );
  });
});
