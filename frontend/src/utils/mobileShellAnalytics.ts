import posthog from 'posthog-js';

export const MOBILE_SHELL_ANALYTICS_EVENT =
  'brickbuilder:mobile-shell-analytics';

type NativeMobileShellInfo = Readonly<{
  platform: 'ios' | 'android';
  version: string;
}>;

declare global {
  interface Window {
    __BRICKBUILDER_NATIVE_APP__?: NativeMobileShellInfo;
  }
}

const ALLOWED_EVENT_NAMES = new Set([
  'mobile_shell_loaded',
  'mobile_shell_navigation_clicked',
  'mobile_shell_back_clicked',
  'mobile_shell_reload_clicked',
  'mobile_shell_external_link_opened',
]);

type AnalyticsProperty = string | number | boolean | null;

type MobileShellEventDetail = {
  eventName: string;
  properties?: Record<string, unknown>;
};

export function isNativeMobileShell(): boolean {
  if (typeof window === 'undefined') return false;

  const shellInfo = window.__BRICKBUILDER_NATIVE_APP__;
  return Boolean(
    shellInfo &&
      (shellInfo.platform === 'ios' || shellInfo.platform === 'android') &&
      typeof shellInfo.version === 'string',
  );
}

function isEventDetail(value: unknown): value is MobileShellEventDetail {
  return Boolean(
    value &&
      typeof value === 'object' &&
      'eventName' in value &&
      typeof value.eventName === 'string' &&
      ALLOWED_EVENT_NAMES.has(value.eventName),
  );
}

function sanitizeProperties(
  properties: Record<string, unknown> | undefined,
): Record<string, AnalyticsProperty> {
  if (!properties) return {};

  return Object.fromEntries(
    Object.entries(properties)
      .filter(([, value]) =>
        value === null ||
        typeof value === 'string' ||
        typeof value === 'number' ||
        typeof value === 'boolean',
      )
      .slice(0, 20),
  ) as Record<string, AnalyticsProperty>;
}

export function captureMobileShellAnalytics(detail: unknown): boolean {
  if (!isEventDetail(detail)) return false;

  posthog.capture(detail.eventName, sanitizeProperties(detail.properties));
  return true;
}

export function registerMobileShellAnalytics(): void {
  window.addEventListener(MOBILE_SHELL_ANALYTICS_EVENT, (event) => {
    captureMobileShellAnalytics((event as CustomEvent<unknown>).detail);
  });
}
