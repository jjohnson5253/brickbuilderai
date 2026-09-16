import React from 'react';
import { Check, ChevronDown, Loader2, Pencil, Sparkles, X } from 'lucide-react';

import {
  LLM_EDIT_REASONING_OPTIONS,
  type LlmEditReasoningLevel,
} from '../utils/llmEditReasoning';

interface ModelEditControlsProps {
  aiDisabled: boolean;
  isAiEditing: boolean;
  isManualEditorOpen: boolean;
  manualLoading: boolean;
  reasoningLevel: LlmEditReasoningLevel;
  onAiEdit: () => void;
  onManualEdit: () => void;
  onReasoningChange: (level: LlmEditReasoningLevel) => void;
}

export function ModelEditControls({
  aiDisabled,
  isAiEditing,
  isManualEditorOpen,
  manualLoading,
  reasoningLevel,
  onAiEdit,
  onManualEdit,
  onReasoningChange,
}: ModelEditControlsProps) {
  const [reasoningMenuOpen, setReasoningMenuOpen] = React.useState(false);
  const reasoningMenuRef = React.useRef<HTMLDivElement | null>(null);
  const reasoningDisabled = aiDisabled || manualLoading;

  React.useEffect(() => {
    if (!reasoningMenuOpen) return;

    const handleDismiss = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent && event.key !== 'Escape') return;
      if (
        event instanceof MouseEvent
        && reasoningMenuRef.current?.contains(event.target as Node)
      ) {
        return;
      }
      setReasoningMenuOpen(false);
    };

    document.addEventListener('mousedown', handleDismiss);
    document.addEventListener('keydown', handleDismiss);
    return () => {
      document.removeEventListener('mousedown', handleDismiss);
      document.removeEventListener('keydown', handleDismiss);
    };
  }, [reasoningMenuOpen]);

  React.useEffect(() => {
    if (reasoningDisabled || isManualEditorOpen) setReasoningMenuOpen(false);
  }, [isManualEditorOpen, reasoningDisabled]);

  if (isManualEditorOpen) {
    return (
      <div className="flex w-full justify-center sm:w-auto">
        <button
          type="button"
          aria-label="Exit block editor"
          onClick={onManualEdit}
          disabled={manualLoading}
          className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border-2 border-[#f44336] bg-[#f44336] px-7 font-semibold text-white shadow-lg shadow-[#f44336]/25 transition-all duration-150 hover:scale-[1.03] hover:border-[#ff6b6b] hover:bg-[#ff6b6b] focus:outline-none focus:ring-2 focus:ring-[#f44336] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto sm:min-w-44"
        >
          <Pencil size={16} />
          Exit Block Editor
        </button>
      </div>
    );
  }

  return (
    <div className="relative flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row">
      <div className="attention-pulse relative flex h-12 w-full min-w-0 rounded-full shadow-lg shadow-[#f44336]/25 sm:w-72">
        <button
          type="button"
          aria-label="AI edit model"
          onClick={onAiEdit}
          disabled={aiDisabled}
          className="relative h-12 min-w-0 flex-1 rounded-full border-2 border-[#f44336] bg-[#f44336] font-semibold text-white transition-colors hover:border-[#ff6b6b] hover:bg-[#ff6b6b] focus:outline-none focus:ring-2 focus:ring-[#f44336] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="absolute left-1/2 top-1/2 inline-flex -translate-x-1/2 -translate-y-1/2 items-center gap-2 whitespace-nowrap">
            {isAiEditing ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                AI editing...
              </>
            ) : (
              <>
                <Sparkles size={16} />
                AI Edit
              </>
            )}
          </span>
        </button>
        <div
          ref={reasoningMenuRef}
          className="absolute right-2 top-1/2 z-20 w-24 -translate-y-1/2"
        >
          {reasoningMenuOpen && (
            <div
              id="llm-thinking-level-menu"
              role="dialog"
              aria-label="Choose thinking level"
              className="absolute bottom-full right-0 mb-2 w-44 overflow-hidden rounded-2xl border border-slate-200 bg-white/95 text-left shadow-2xl shadow-black/25 backdrop-blur-md"
            >
              <div className="flex items-center justify-between border-b border-slate-200 px-3.5 py-2.5">
                <h3 className="text-sm font-semibold text-slate-900">Thinking level</h3>
                <button
                  type="button"
                  onClick={() => setReasoningMenuOpen(false)}
                  aria-label="Close thinking level"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-full text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-800"
                >
                  <X size={15} />
                </button>
              </div>
              <div className="space-y-1.5 p-2.5">
                {LLM_EDIT_REASONING_OPTIONS.map((option) => {
                  const isSelected = option.value === reasoningLevel;
                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => {
                        setReasoningMenuOpen(false);
                        if (!isSelected) onReasoningChange(option.value);
                      }}
                      className={`flex w-full items-center justify-between rounded-xl border px-3 py-2 text-xs font-semibold capitalize transition-colors ${
                        isSelected
                          ? 'border-[#f44336]/60 bg-red-50 text-[#c62828]'
                          : 'border-slate-200 bg-white text-slate-700 hover:border-[#f44336]/40 hover:bg-red-50'
                      }`}
                    >
                      {option.value}
                      {isSelected && <Check aria-hidden="true" size={14} />}
                    </button>
                  );
                })}
              </div>
            </div>
          )}
          <button
            type="button"
            aria-label="Thinking level"
            aria-controls="llm-thinking-level-menu"
            aria-expanded={reasoningMenuOpen}
            aria-haspopup="dialog"
            disabled={reasoningDisabled}
            onClick={() => setReasoningMenuOpen((open) => !open)}
            className="inline-flex h-8 w-full cursor-pointer items-center justify-center rounded-full border border-white/70 bg-white/95 px-6 text-center text-xs font-semibold lowercase text-[#c62828] shadow-sm outline-none transition-all duration-150 hover:bg-white focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-[#f44336] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {reasoningLevel}
          </button>
          <ChevronDown
            aria-hidden="true"
            size={13}
            className={`pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[#c62828] transition-transform duration-200 ${
              reasoningMenuOpen ? 'rotate-180' : ''
            }`}
          />
        </div>
      </div>

      <button
        type="button"
        aria-label="Manual edit model"
        onClick={onManualEdit}
        disabled={manualLoading}
        className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-full border-2 border-slate-300 bg-white px-7 font-semibold text-slate-800 transition-all duration-150 hover:scale-[1.03] hover:border-[#f44336] hover:text-[#f44336] hover:shadow-lg disabled:cursor-not-allowed disabled:opacity-70 sm:w-auto sm:min-w-44"
      >
        {manualLoading ? (
          <>
            <Loader2 size={16} className="animate-spin" />
            Loading...
          </>
        ) : (
          <>
            <Pencil size={16} />
            Manual Edit
          </>
        )}
      </button>
    </div>
  );
}
