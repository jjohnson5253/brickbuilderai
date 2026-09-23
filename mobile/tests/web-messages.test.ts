import { describe, expect, it } from 'vitest';

import { parseChangeRequestAccessMessage } from '../src/webMessages';

describe('parseChangeRequestAccessMessage', () => {
  it('accepts explicit access state from the web app', () => {
    expect(parseChangeRequestAccessMessage(JSON.stringify({
      type: 'brickbuilder:change-request-access',
      enabled: true,
    }))).toBe(true);
    expect(parseChangeRequestAccessMessage(JSON.stringify({
      type: 'brickbuilder:change-request-access',
      enabled: false,
    }))).toBe(false);
  });

  it('rejects malformed or unrelated messages', () => {
    expect(parseChangeRequestAccessMessage('not json')).toBeNull();
    expect(parseChangeRequestAccessMessage(JSON.stringify({
      type: 'other-message',
      enabled: true,
    }))).toBeNull();
    expect(parseChangeRequestAccessMessage(JSON.stringify({
      type: 'brickbuilder:change-request-access',
      enabled: 'yes',
    }))).toBeNull();
  });
});
