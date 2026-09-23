import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_AUTOSAVE_INTERVAL_MS,
  useDirtyAutosave,
} from '../src/hooks/useDirtyAutosave';

interface HarnessProps {
  hasChanges: boolean;
  isSaving: boolean;
  onSave: () => void;
}

function AutosaveHarness(props: HarnessProps) {
  useDirtyAutosave(props);
  return null;
}

describe('useDirtyAutosave', () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it('saves dirty editor content after five seconds', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    const root = createRoot(container);
    const onSave = vi.fn();

    try {
      act(() => {
        root.render(
          <AutosaveHarness hasChanges isSaving={false} onSave={onSave} />,
        );
      });

      act(() => {
        vi.advanceTimersByTime(DEFAULT_AUTOSAVE_INTERVAL_MS - 1);
      });
      expect(onSave).not.toHaveBeenCalled();

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(onSave).toHaveBeenCalledOnce();
    } finally {
      act(() => root.unmount());
    }
  });

  it('waits until an active save finishes before scheduling the next save', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    const root = createRoot(container);
    const onSave = vi.fn();

    try {
      act(() => {
        root.render(
          <AutosaveHarness hasChanges isSaving onSave={onSave} />,
        );
      });
      act(() => {
        vi.advanceTimersByTime(DEFAULT_AUTOSAVE_INTERVAL_MS);
      });
      expect(onSave).not.toHaveBeenCalled();

      act(() => {
        root.render(
          <AutosaveHarness hasChanges isSaving={false} onSave={onSave} />,
        );
      });
      act(() => {
        vi.advanceTimersByTime(DEFAULT_AUTOSAVE_INTERVAL_MS);
      });
      expect(onSave).toHaveBeenCalledOnce();
    } finally {
      act(() => root.unmount());
    }
  });

  it('uses the latest save callback without delaying the existing timer', () => {
    vi.useFakeTimers();
    const container = document.createElement('div');
    const root = createRoot(container);
    const firstSave = vi.fn();
    const latestSave = vi.fn();

    try {
      act(() => {
        root.render(
          <AutosaveHarness hasChanges isSaving={false} onSave={firstSave} />,
        );
      });
      act(() => {
        vi.advanceTimersByTime(2_000);
      });
      act(() => {
        root.render(
          <AutosaveHarness hasChanges isSaving={false} onSave={latestSave} />,
        );
      });
      act(() => {
        vi.advanceTimersByTime(3_000);
      });

      expect(firstSave).not.toHaveBeenCalled();
      expect(latestSave).toHaveBeenCalledOnce();
    } finally {
      act(() => root.unmount());
    }
  });
});
