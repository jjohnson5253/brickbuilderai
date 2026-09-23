export const DEFAULT_WEB_APP_URL = 'https://brickbuilder.ai';

const LOCAL_DEVELOPMENT_HOSTS = new Set(['localhost', '127.0.0.1', '[::1]']);

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
