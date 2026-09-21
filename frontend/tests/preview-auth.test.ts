import { describe, expect, it } from 'vitest';
import { previewLoginFromSearch, redeemPreviewLogin, stripPreviewLogin } from '../src/utils/previewAuth';

describe('preview magic-link handoff', () => {
  it('accepts a Supabase magic-link token and preserves the request id', () => {
    expect(previewLoginFromSearch('?change_request=req-1&preview_login=1&token_hash=hash&type=magiclink'))
      .toEqual({ token_hash: 'hash', type: 'magiclink' });
    expect(stripPreviewLogin('?change_request=req-1&preview_login=1&token_hash=hash&type=magiclink'))
      .toBe('?change_request=req-1');
  });

  it('rejects incomplete and unrelated query strings', () => {
    expect(previewLoginFromSearch('?preview_login=1&type=magiclink')).toBeNull();
    expect(previewLoginFromSearch('?token_hash=hash&type=recovery')).toBeNull();
  });

  it('reports verification failures without rejecting app initialization', async () => {
    const login = { token_hash: 'hash', type: 'magiclink' as const };
    await expect(redeemPreviewLogin({
      verifyOtp: async () => ({ error: null }),
    }, login)).resolves.toBeNull();
    await expect(redeemPreviewLogin({
      verifyOtp: async () => ({ error: { message: 'Token expired' } }),
    }, login)).resolves.toBe('Token expired');
    await expect(redeemPreviewLogin({
      verifyOtp: async () => { throw new Error('Network unavailable'); },
    }, login)).resolves.toBe('Network unavailable');
  });
});
