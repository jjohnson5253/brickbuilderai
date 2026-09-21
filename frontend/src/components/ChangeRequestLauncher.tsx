import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from 'react';
import { CheckCircle2, ImagePlus, Loader2, WandSparkles, X } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import {
  approveChangeRequest, checkChangeRequestAccess, getChangeRequest,
  submitChangeRequest, type ChangeRequestState,
} from '../services/changeRequestApi';

const requestIdFromUrl = () => new URLSearchParams(window.location.search).get('change_request') || undefined;

type ChangeRequestContextValue = {
  enabled: boolean;
  openForm: () => void;
};

const ChangeRequestContext = createContext<ChangeRequestContextValue>({
  enabled: false,
  openForm: () => {},
});

export function ChangeRequestProvider({ children }: { children: ReactNode }) {
  const { session, loading } = useAuth();
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [description, setDescription] = useState('');
  const [files, setFiles] = useState<File[]>([]);
  const [request, setRequest] = useState<ChangeRequestState | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const requestId = useMemo(requestIdFromUrl, []);
  const token = session?.access_token;

  useEffect(() => {
    if (loading || !token) { setEnabled(false); return; }
    let active = true;
    void checkChangeRequestAccess(token).then(async (allowed) => {
      if (!active) return;
      setEnabled(allowed);
      if (!allowed) return;
      const state = await getChangeRequest(token, requestId).catch(() => null);
      if (!active) return;
      setRequest(state);
      if (requestId) setOpen(true);
    });
    return () => { active = false; };
  }, [loading, requestId, token]);

  const submit = async () => {
    if (!token) { setMessage('Sign in to request a change.'); return; }
    if (!description.trim()) { setMessage('Describe what you want to change.'); return; }
    setBusy(true); setMessage('');
    try {
      const result = await submitChangeRequest(token, description, files, request?.id || requestId);
      setRequest((current) => current ? { ...current, status: 'working' } : {
        id: result.id, status: 'working', branch: null, pr_number: null,
        preview_url: null, revision: 1,
      });
      setDescription(''); setFiles([]);
      setMessage('Copilot is working on it. You will receive an email when the preview is ready.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not submit the change.');
    } finally { setBusy(false); }
  };

  const approve = async () => {
    if (!token) { setMessage('Sign in to approve this change.'); return; }
    if (!request?.id) return;
    setBusy(true); setMessage('');
    try {
      const result = await approveChangeRequest(token, request.id);
      setRequest({ ...request, status: 'approved' });
      setMessage(`Merged into staging. Main pull request: ${result.main_pr_url || 'email pending'}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Could not approve the change.');
    } finally { setBusy(false); }
  };

  return <ChangeRequestContext.Provider value={{
    enabled: enabled && Boolean(token),
    openForm: () => setOpen(true),
  }}>
    {children}
    {enabled && token && open && <div className="fixed inset-0 z-[80] flex items-end justify-center bg-slate-950/55 p-3 sm:items-center">
      <section className="max-h-[92vh] w-full max-w-xl overflow-y-auto rounded-2xl bg-white p-5 shadow-2xl sm:p-7" role="dialog" aria-modal="true" aria-labelledby="change-request-title">
        <div className="mb-5 flex items-start justify-between gap-4">
          <div>
            <h2 id="change-request-title" className="text-xl font-extrabold text-slate-950">What do you want to change?</h2>
            <p className="mt-1 text-sm text-slate-600">Describe the result and attach up to four screenshots.</p>
          </div>
          <button type="button" aria-label="Close" onClick={() => setOpen(false)} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </div>

        {request?.status === 'preview_ready' && <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <p className="font-semibold text-emerald-950">This preview is ready for your review.</p>
          <button type="button" disabled={busy} onClick={approve} className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-50">
            <CheckCircle2 className="h-4 w-4" /> Looks good — merge to staging
          </button>
        </div>}

        <label className="block text-sm font-bold text-slate-800" htmlFor="change-description">Change description</label>
        <textarea id="change-description" maxLength={8000} rows={6} value={description} onChange={(event) => setDescription(event.target.value)}
          placeholder="Explain what should change and what the finished result should look like."
          className="mt-2 w-full rounded-xl border border-slate-300 p-3 text-sm outline-none focus:border-red-500 focus:ring-2 focus:ring-red-100" />

        <label className="mt-4 flex cursor-pointer items-center justify-center gap-2 rounded-xl border border-dashed border-slate-300 px-4 py-4 text-sm font-semibold text-slate-700 hover:bg-slate-50">
          <ImagePlus className="h-5 w-5" /> Add screenshots
          <input className="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple
            onChange={(event) => setFiles(Array.from(event.target.files || []).slice(0, 4))} />
        </label>
        {files.length > 0 && <p className="mt-2 text-xs text-slate-600">{files.map((file) => file.name).join(', ')}</p>}

        <p className="mt-4 text-xs text-slate-500">Do not include passwords, payment details, or private customer information.</p>
        {message && <p className="mt-4 rounded-lg bg-slate-100 p-3 text-sm text-slate-800" role="status">{message}</p>}
        <button type="button" disabled={busy || !description.trim()} onClick={submit}
          className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#f44336] px-4 py-3 font-bold text-white hover:bg-red-600 disabled:opacity-50">
          {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <WandSparkles className="h-5 w-5" />}
          {request?.status === 'preview_ready' ? 'Request another revision' : 'Send change request'}
        </button>
      </section>
    </div>}
  </ChangeRequestContext.Provider>;
}

export function ChangeRequestMenuItem({ onSelect }: { onSelect?: () => void }) {
  const { enabled, openForm } = useContext(ChangeRequestContext);
  if (!enabled) return null;

  return (
    <button
      type="button"
      onClick={() => {
        onSelect?.();
        openForm();
      }}
      className="flex w-full cursor-pointer items-center gap-2 border-none bg-transparent px-4 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
    >
      <WandSparkles className="h-4 w-4" />
      Request an app change
    </button>
  );
}
