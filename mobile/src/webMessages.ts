export const CHANGE_REQUEST_ACCESS_MESSAGE =
  'brickbuilder:change-request-access';
export const OPEN_CHANGE_REQUEST_EVENT =
  'brickbuilder:open-change-request';

export function parseChangeRequestAccessMessage(raw: string): boolean | null {
  try {
    const value = JSON.parse(raw) as Record<string, unknown>;
    if (
      value?.type !== CHANGE_REQUEST_ACCESS_MESSAGE ||
      typeof value.enabled !== 'boolean'
    ) {
      return null;
    }
    return value.enabled;
  } catch {
    return null;
  }
}
