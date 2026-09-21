import { describe, expect, it } from 'vitest';
import { resolveBrickbuilderGithubRepoUrl } from '../src/constants/urls';

describe('resolveBrickbuilderGithubRepoUrl', () => {
  it('keeps a configured URL when it matches the expected GitHub repository', () => {
    const repoUrl = resolveBrickbuilderGithubRepoUrl(
      'https://github.com/jjohnson5253/brickbuilderai/',
    );

    expect(repoUrl).toBe('https://github.com/jjohnson5253/brickbuilderai');
  });

  it('falls back to default when configured URL is not the expected GitHub repository', () => {
    const repoUrl = resolveBrickbuilderGithubRepoUrl(
      'https://example.com/not-brickbuilder',
    );

    expect(repoUrl).toBe('https://github.com/jjohnson5253/brickbuilderai');
  });

  it('accepts mixed-case GitHub hostnames and trims surrounding whitespace', () => {
    const repoUrl = resolveBrickbuilderGithubRepoUrl(
      '  https://GitHub.com/jjohnson5253/brickbuilderai/  ',
    );

    expect(repoUrl).toBe('https://github.com/jjohnson5253/brickbuilderai');
  });
});
