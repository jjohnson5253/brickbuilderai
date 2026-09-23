import { beforeEach, describe, expect, it, vi } from 'vitest';

import posthog from 'posthog-js';
import { captureMobileShellAnalytics } from '../src/utils/mobileShellAnalytics';

vi.mock('posthog-js', () => ({
  default: {
    capture: vi.fn(),
  },
}));

describe('mobile shell analytics', () => {
  beforeEach(() => {
    vi.mocked(posthog.capture).mockClear();
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
});
