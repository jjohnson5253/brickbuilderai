import { describe, expect, it } from 'vitest';

import {
  DEFAULT_WEB_APP_URL,
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
