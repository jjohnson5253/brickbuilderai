import { afterEach, beforeEach, describe, expect, it } from 'vitest';

import middleware from '../middleware';

const originalEnvironment = { ...process.env };

function loginRequest(password: string): Request {
  return new Request('https://example.com/__preview-auth', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `password=${encodeURIComponent(password)}`,
  });
}

describe('preview password middleware', () => {
  beforeEach(() => {
    process.env.VERCEL = '1';
    process.env.VERCEL_GIT_COMMIT_REF = 'feature/password-gate';
    process.env.PREVIEW_PASSWORD = 'test-password';
  });

  afterEach(() => {
    process.env = { ...originalEnvironment };
  });

  it('does not run outside Vercel', async () => {
    delete process.env.VERCEL;

    await expect(middleware(new Request('https://example.com/'))).resolves.toBeUndefined();
  });

  it('does not run for the main branch', async () => {
    process.env.VERCEL_GIT_COMMIT_REF = 'main';

    await expect(middleware(new Request('https://example.com/'))).resolves.toBeUndefined();
  });

  it('fails closed when a preview password is not configured', async () => {
    delete process.env.PREVIEW_PASSWORD;

    const response = await middleware(new Request('https://example.com/'));

    expect(response?.status).toBe(503);
  });

  it('shows a password-only form for an unauthenticated preview request', async () => {
    const response = await middleware(new Request('https://example.com/dashboard'));
    const body = await response?.text();

    expect(response?.status).toBe(200);
    expect(body).toContain('name="password"');
    expect(body).not.toContain('name="username"');
    expect(body).not.toContain('test-password');
  });

  it('rejects an incorrect password', async () => {
    const response = await middleware(loginRequest('wrong-password'));

    expect(response?.status).toBe(401);
    await expect(response?.text()).resolves.toContain('Incorrect password');
  });

  it('sets a secure cookie after accepting the password', async () => {
    const response = await middleware(loginRequest('test-password'));

    expect(response?.status).toBe(303);
    expect(response?.headers.get('location')).toBe('/');
    expect(response?.headers.get('set-cookie')).toMatch(
      /^brickbuilder_preview_auth=[a-f0-9]{64}; Path=\/; HttpOnly; Secure; SameSite=Strict;/,
    );
    expect(response?.headers.get('set-cookie')).not.toContain('test-password');
  });

  it('allows requests with the cookie issued after authentication', async () => {
    const loginResponse = await middleware(loginRequest('test-password'));
    const cookie = loginResponse?.headers.get('set-cookie')?.split(';', 1)[0];

    const response = await middleware(
      new Request('https://example.com/dashboard', {
        headers: { Cookie: cookie ?? '' },
      }),
    );

    expect(response).toBeUndefined();
  });
});
