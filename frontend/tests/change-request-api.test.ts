import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  approveChangeRequest, checkChangeRequestAccess, getChangeRequest, submitChangeRequest,
} from '../src/services/changeRequestApi';

afterEach(() => vi.restoreAllMocks());

function response(body: unknown, ok = true) {
  return Promise.resolve({ ok, json: async () => body } as Response);
}

describe('change request API', () => {
  it('checks access without exposing the allowlist', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ enabled: true }));
    await expect(checkChangeRequestAccess('token')).resolves.toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(expect.stringContaining('/functions/v1/change-request'),
      expect.objectContaining({ method: 'POST' }));
    fetchMock.mockImplementation(() => response({ error: 'denied' }, false));
    await expect(checkChangeRequestAccess('token')).resolves.toBe(false);
  });

  it('does not load an unrelated request from the main app', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch');
    await expect(getChangeRequest('token')).resolves.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('loads an explicitly linked preview request', async () => {
    const state = { id: 'req-1', status: 'preview_ready', branch: 'copilot/change' };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ request: state }));
    await expect(getChangeRequest('token', 'req-1')).resolves.toEqual(state);
    expect(JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body)))
      .toMatchObject({ action: 'status', request_id: 'req-1' });
  });

  it('submits text and screenshots as a new request from main', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ id: 'req-1', status: 'working' }));
    const image = new File(['image'], 'idea.png', { type: 'image/png' });
    await submitChangeRequest('token', 'Make the editor clearer', [image]);
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const form = init.body as FormData;
    expect(form.get('branch')).toBe('main');
    expect(form.get('description')).toBe('Make the editor clearer');
    expect(form.getAll('screenshots')).toEqual([image]);
  });

  it('sends approval with the authenticated revision context', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => response({ status: 'approved' }));
    await approveChangeRequest('token', 'req-1');
    const body = JSON.parse(String((fetchMock.mock.calls[0][1] as RequestInit).body));
    expect(body).toMatchObject({ action: 'approve', request_id: 'req-1', branch: 'main' });
  });

  it('surfaces server and malformed-response failures', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementationOnce(() => response({ error: 'Approval denied' }, false));
    await expect(approveChangeRequest('token', 'req-1')).rejects.toThrow('Approval denied');

    vi.mocked(globalThis.fetch).mockImplementationOnce(() => Promise.resolve({
      ok: false, json: async () => { throw new Error('bad json'); },
    } as Response));
    await expect(submitChangeRequest('token', 'Change it', [])).rejects.toThrow('Change request failed');
  });
});
