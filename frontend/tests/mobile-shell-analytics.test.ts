import { beforeEach, describe, expect, it, vi } from 'vitest';

import posthog from 'posthog-js';
import {
  captureMobileShellAnalytics,
  getNativeMobileShellInfo,
  isNativeMobileShell,
  notifyMobileChangeRequestAccess,
} from '../src/utils/mobileShellAnalytics';

vi.mock('posthog-js', () => ({
  default: {
    capture: vi.fn(),
  },
}));

describe('mobile shell analytics', () => {
  beforeEach(() => {
    vi.mocked(posthog.capture).mockClear();
    delete window.__BRICKBUILDER_NATIVE_APP__;
    delete window.ReactNativeWebView;
  });

  it('recognizes the validated native shell marker', () => {
    expect(isNativeMobileShell()).toBe(false);

    window.__BRICKBUILDER_NATIVE_APP__ = Object.freeze({
      platform: 'ios',
      version: '0.1.0',
    });

    expect(isNativeMobileShell()).toBe(true);
  });

  it('validates feedback-build context and notifies the native bridge', () => {
    const postMessage = vi.fn();
    window.__BRICKBUILDER_NATIVE_APP__ = Object.freeze({
      platform: 'ios',
      version: '0.1.0',
      changeRequest: {
        requestId: 'request-1',
        branch: 'copilot/change-request-1',
        sha: '0123456789abcdef',
      },
    });
    window.ReactNativeWebView = { postMessage };

    expect(getNativeMobileShellInfo()?.changeRequest?.requestId).toBe('request-1');
    notifyMobileChangeRequestAccess(true);
    expect(postMessage).toHaveBeenCalledWith(JSON.stringify({
      type: 'brickbuilder:change-request-access',
      enabled: true,
    }));
  });

  it('captures allow-listed native shell interactions', () => {
    expect(
      captureMobileShellAnalytics({
        eventName: 'mobile_shell_navigation_clicked',
        properties: { destination: 'dashboard', nested: { ignored: true } },
      }),
    ).toBe(true);

    expect(posthog.capture).toHaveBeenCalledWith(
      'mobile_shell_navigation_clicked',
      { destination: 'dashboard' },
    );
  });

  it('rejects arbitrary events from web content', () => {
    expect(
      captureMobileShellAnalytics({
        eventName: 'unexpected_event',
        properties: { secret: 'value' },
      }),
    ).toBe(false);
    expect(posthog.capture).not.toHaveBeenCalled();
  });

  it('captures the native change-request button', () => {
    expect(captureMobileShellAnalytics({
      eventName: 'mobile_shell_change_request_clicked',
    })).toBe(true);
    expect(posthog.capture).toHaveBeenCalledWith(
      'mobile_shell_change_request_clicked',
      {},
    );
  });
});
