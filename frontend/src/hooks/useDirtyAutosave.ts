import { useEffect, useRef } from 'react';

interface UseDirtyAutosaveOptions {
  hasChanges: boolean;
  isSaving: boolean;
  onSave: () => void | Promise<void>;
  intervalMs?: number;
}

export const DEFAULT_AUTOSAVE_INTERVAL_MS = 5_000;

/**
 * Saves once a dirty editor has remained eligible for the configured interval.
 * Failed saves remain dirty and are retried on the next interval.
 */
export function useDirtyAutosave({
  hasChanges,
  isSaving,
  onSave,
  intervalMs = DEFAULT_AUTOSAVE_INTERVAL_MS,
}: UseDirtyAutosaveOptions) {
  const onSaveRef = useRef(onSave);

  useEffect(() => {
    onSaveRef.current = onSave;
  }, [onSave]);

  useEffect(() => {
    if (!hasChanges || isSaving) return;

    const timeoutId = window.setTimeout(() => {
      void onSaveRef.current();
    }, intervalMs);

    return () => window.clearTimeout(timeoutId);
  }, [hasChanges, intervalMs, isSaving]);
}
