import { describe, expect, it } from 'vitest';

import {
  DEFAULT_WEB_APP_URL,
  normalizeMobileChangeRequest,
  normalizeWebAppUrl,
} from '../src/config';

describe('normalizeWebAppUrl', () => {
  it('uses the production app when no override is supplied', () => {
    expect(normalizeWebAppUrl()).toBe(DEFAULT_WEB_APP_URL);
  });

  it('normalizes a secure preview URL to its origin', () => {
    expect(normalizeWebAppUrl(' https://preview.example.com/dashboard ')).toBe(
      'https://preview.example.com',
    );
  });

  it('allows localhost over HTTP for simulator development', () => {
    expect(normalizeWebAppUrl('http://localhost:3000')).toBe(
      'http://localhost:3000',
    );
  });

  it('rejects insecure remote origins', () => {
    expect(() => normalizeWebAppUrl('http://example.com')).toThrow(/HTTPS/);
  });
});

describe('normalizeMobileChangeRequest', () => {
  it('keeps an exact feedback build context', () => {
    expect(normalizeMobileChangeRequest({
      requestId: '4d946c59-b45e-4cd2-a147-1e3495366a04',
      branch: 'copilot/change-request-12',
      sha: '0123456789abcdef0123456789abcdef01234567',
    })).toEqual({
      requestId: '4d946c59-b45e-4cd2-a147-1e3495366a04',
      branch: 'copilot/change-request-12',
      sha: '0123456789abcdef0123456789abcdef01234567',
    });
  });

  it('falls back to production context when feedback values are invalid', () => {
    expect(normalizeMobileChangeRequest({
      requestId: 'not-a-uuid',
      branch: 'main; rm -rf',
      sha: 'latest',
    })).toEqual({ requestId: '', branch: 'main', sha: '' });
  });
});
