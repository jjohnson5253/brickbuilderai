const supabaseUrl = String(import.meta.env.VITE_SUPABASE_URL || '').replace(/\/$/, '');
export const CHANGE_REQUEST_ENDPOINT = `${supabaseUrl}/functions/v1/change-request`;
export const CHANGE_REQUEST_BRANCH = import.meta.env.VITE_CHANGE_REQUEST_BRANCH || 'main';
export const CHANGE_REQUEST_SHA = import.meta.env.VITE_CHANGE_REQUEST_SHA || '';

export type ChangeRequestState = {
  id: string;
  status: 'queued' | 'working' | 'preview_ready' | 'approved' | 'failed';
  branch: string | null;
  pr_number: number | null;
  preview_url: string | null;
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
  if (!requestId && ['main', 'staging'].includes(CHANGE_REQUEST_BRANCH)) return null;
  const payload = await jsonRequest(token, {
    action: 'status', request_id: requestId,
    branch: CHANGE_REQUEST_BRANCH,
  });
  return (payload.request || null) as ChangeRequestState | null;
}

export async function submitChangeRequest(token: string, description: string, files: File[],
  requestId?: string) {
  const form = new FormData();
  form.set('description', description);
  form.set('branch', requestId && !['main', 'staging'].includes(CHANGE_REQUEST_BRANCH)
    ? CHANGE_REQUEST_BRANCH : 'main');
  form.set('deployment_sha', CHANGE_REQUEST_SHA);
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
  return jsonRequest(token, {
    action: 'approve', request_id: requestId,
    branch: CHANGE_REQUEST_BRANCH, deployment_sha: CHANGE_REQUEST_SHA,
  });
}
