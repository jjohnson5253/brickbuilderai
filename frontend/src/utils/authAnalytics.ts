import posthog from 'posthog-js';

export type AuthMethod = 'magic_link' | 'password';
export type AuthSurface = 'login_modal' | 'login_page';

export function trackAuthMethodSelected(surface: AuthSurface, method: AuthMethod): void {
  posthog.capture('auth_method_selected', {
    surface,
    method,
  });
}

export function trackPasswordLoginSubmitted(surface: AuthSurface): void {
  posthog.capture('auth_password_login_submitted', {
    surface,
    method: 'password',
  });
}
