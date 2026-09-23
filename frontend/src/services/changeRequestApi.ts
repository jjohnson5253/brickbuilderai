import { getNativeMobileShellInfo } from '../utils/mobileShellAnalytics';

const supabaseUrl = String(import.meta.env.VITE_SUPABASE_URL || '').replace(/\/$/, '');
export const CHANGE_REQUEST_ENDPOINT = `${supabaseUrl}/functions/v1/change-request`;
export const CHANGE_REQUEST_BRANCH = import.meta.env.VITE_CHANGE_REQUEST_BRANCH || 'main';
export const CHANGE_REQUEST_SHA = import.meta.env.VITE_CHANGE_REQUEST_SHA || '';

export type ChangeRequestTarget = 'web' | 'ios';

export type ChangeRequestRuntimeContext = Readonly<{
  target: ChangeRequestTarget;
  requestId?: string;
  branch: string;
  sha: string;
}>;

export function getChangeRequestRuntimeContext(): ChangeRequestRuntimeContext {
  const linkedRequestId = typeof window === 'undefined'
    ? undefined
    : new URLSearchParams(window.location.search).get('change_request') || undefined;
  const nativeShell = getNativeMobileShellInfo();
  if (nativeShell) {
    return {
      target: 'ios',
      requestId: nativeShell.changeRequest?.requestId || linkedRequestId,
      branch: nativeShell.changeRequest?.branch || 'main',
      sha: nativeShell.changeRequest?.sha || '',
    };
  }

  return {
    target: 'web',
    requestId: linkedRequestId,
    branch: CHANGE_REQUEST_BRANCH,
    sha: CHANGE_REQUEST_SHA,
  };
}

export type ChangeRequestState = {
  id: string;
  status: 'queued' | 'working' | 'building' | 'preview_ready' | 'approved' | 'failed';
  target: ChangeRequestTarget;
  branch: string | null;
  pr_number: number | null;
  preview_url: string | null;
  mobile_build_url: string | null;
  testflight_url: string | null;
  notified_sha: string | null;
  revision: number;
};

async function jsonRequest(token: string, body: Record<string, unknown>) {
  const response = await fetch(CHANGE_REQUEST_ENDPOINT, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || 'Change request failed.');
  return payload;
}

export async function checkChangeRequestAccess(token: string): Promise<boolean> {
  try { await jsonRequest(token, { action: 'access' }); return true; }
  catch { return false; }
}

export async function getChangeRequest(token: string, requestId?: string) {
  const runtime = getChangeRequestRuntimeContext();
  const resolvedRequestId = requestId || runtime.requestId;
  if (!resolvedRequestId && ['main', 'staging'].includes(runtime.branch)) return null;
  const payload = await jsonRequest(token, {
    action: 'status', request_id: resolvedRequestId,
    branch: runtime.branch,
  });
  return (payload.request || null) as ChangeRequestState | null;
}

export async function submitChangeRequest(token: string, description: string, files: File[],
  requestId?: string) {
  const runtime = getChangeRequestRuntimeContext();
  const form = new FormData();
  form.set('description', description);
  form.set('target', runtime.target);
  form.set('branch', requestId && !['main', 'staging'].includes(runtime.branch)
    ? runtime.branch : 'main');
  form.set('deployment_sha', runtime.sha);
  form.set('no_phi', 'yes');
  if (requestId) form.set('request_id', requestId);
  for (const file of files) form.append('screenshots', file);
  const response = await fetch(CHANGE_REQUEST_ENDPOINT, {
    method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || 'Change request failed.');
  return payload as { id: string; status: string };
}

export async function approveChangeRequest(token: string, requestId: string) {
  const runtime = getChangeRequestRuntimeContext();
  return jsonRequest(token, {
    action: 'approve', request_id: requestId,
    branch: runtime.branch, deployment_sha: runtime.sha,
  });
}
