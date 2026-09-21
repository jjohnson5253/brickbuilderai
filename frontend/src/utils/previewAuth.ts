export type PreviewLogin = { token_hash: string; type: 'magiclink' | 'email' };

type PreviewAuthClient = {
  verifyOtp(login: PreviewLogin): Promise<{ error: { message?: string } | null }>;
};

export function previewLoginFromSearch(search: string): PreviewLogin | null {
  const query = new URLSearchParams(search);
  const tokenHash = query.get('token_hash');
  const type = query.get('type');
  if (query.get('preview_login') !== '1' || !tokenHash
      || (type !== 'magiclink' && type !== 'email')) return null;
  return { token_hash: tokenHash, type };
}

export function stripPreviewLogin(search: string): string {
  const query = new URLSearchParams(search);
  for (const key of ['preview_login', 'token_hash', 'type']) query.delete(key);
  const rest = query.toString();
  return rest ? `?${rest}` : '';
}

export async function redeemPreviewLogin(auth: PreviewAuthClient, login: PreviewLogin) {
  try {
    const { error } = await auth.verifyOtp(login);
    return error?.message || null;
  } catch (error) {
    return error instanceof Error ? error.message : 'Preview sign-in failed.';
  }
}
