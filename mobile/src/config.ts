export const DEFAULT_WEB_APP_URL = 'https://brickbuilder.ai';

const LOCAL_DEVELOPMENT_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);
const CHANGE_REQUEST_BRANCH = /^[a-zA-Z0-9._/-]{1,150}$/;
const COMMIT_SHA = /^[0-9a-f]{40}$/i;
const REQUEST_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export type MobileChangeRequestContext = Readonly<{
  requestId: string;
  branch: string;
  sha: string;
}>;

export function normalizeWebAppUrl(candidate?: string): string {
  const configuredUrl = candidate?.trim() || DEFAULT_WEB_APP_URL;
  let parsed: URL;

  try {
    parsed = new URL(configuredUrl);
  } catch {
    throw new Error('EXPO_PUBLIC_WEB_APP_URL must be a valid absolute URL.');
  }

  const isSecure = parsed.protocol === 'https:';
  const isLocalDevelopment =
    parsed.protocol === 'http:' && LOCAL_DEVELOPMENT_HOSTS.has(parsed.hostname);

  if (!isSecure && !isLocalDevelopment) {
    throw new Error(
      'EXPO_PUBLIC_WEB_APP_URL must use HTTPS (HTTP is allowed only for localhost).',
    );
  }

  return parsed.origin;
}

export const WEB_APP_URL = normalizeWebAppUrl(
  process.env.EXPO_PUBLIC_WEB_APP_URL,
);

export function normalizeMobileChangeRequest(
  values: Partial<MobileChangeRequestContext> = {},
): MobileChangeRequestContext {
  const requestId = String(values.requestId || '');
  const branch = String(values.branch || 'main');
  const sha = String(values.sha || '').toLowerCase();

  if (branch === 'main') {
    return { requestId: '', branch: 'main', sha: '' };
  }
  if (!REQUEST_ID.test(requestId) || !CHANGE_REQUEST_BRANCH.test(branch) || !COMMIT_SHA.test(sha)) {
    return { requestId: '', branch: 'main', sha: '' };
  }
  return { requestId, branch, sha };
}

export const MOBILE_CHANGE_REQUEST = normalizeMobileChangeRequest({
  requestId: process.env.EXPO_PUBLIC_CHANGE_REQUEST_ID,
  branch: process.env.EXPO_PUBLIC_GIT_BRANCH,
  sha: process.env.EXPO_PUBLIC_GIT_SHA,
});
