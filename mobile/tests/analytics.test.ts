import { describe, expect, it } from 'vitest';

import {
  MOBILE_ANALYTICS_EVENT,
  createAnalyticsDispatchScript,
  createNativeBootstrapScript,
} from '../src/analytics';

describe('mobile analytics bridge', () => {
  it('serializes event data without interpolating executable input', () => {
    const script = createAnalyticsDispatchScript(
      'mobile_shell_navigation_clicked',
      { destination: 'dashboard"; alert(1); //' },
    );

    expect(script).toContain(JSON.stringify(MOBILE_ANALYTICS_EVENT));
    expect(script).toContain('\\"; alert(1); //');
    expect(script).not.toContain('destination: dashboard');
  });

  it('marks the page as native and hides unsupported OAuth UI', () => {
    const script = createNativeBootstrapScript('ios');

    expect(script).toContain('__BRICKBUILDER_NATIVE_APP__');
    expect(script).toContain('[data-native-mobile-hidden="true"]');
    expect(script).toContain('"platform":"ios"');
  });
});
