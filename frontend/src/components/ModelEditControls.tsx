import React from 'react';
import { ChevronDown, Loader2, Pencil, Sparkles } from 'lucide-react';

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
    <div className="flex w-full flex-col items-center justify-center gap-3 sm:w-auto sm:flex-row">
      <div className="attention-pulse relative flex h-12 w-full min-w-0 rounded-full shadow-lg shadow-[#f44336]/25 sm:w-auto sm:min-w-56">
        <button
          type="button"
          aria-label="AI edit model"
          onClick={onAiEdit}
          disabled={aiDisabled}
          className="inline-flex h-12 min-w-0 flex-1 items-center justify-center gap-2 rounded-full border-2 border-[#f44336] bg-[#f44336] pl-5 pr-[7.25rem] font-semibold text-white transition-colors hover:border-[#ff6b6b] hover:bg-[#ff6b6b] focus:outline-none focus:ring-2 focus:ring-[#f44336] focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 sm:pl-7"
        >
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
        </button>
        <div className="absolute right-2 top-1/2 w-24 -translate-y-1/2">
          <label htmlFor="llm-thinking-level" className="sr-only">
            Thinking level
          </label>
          <select
            id="llm-thinking-level"
            aria-label="Thinking level"
            value={reasoningLevel}
            disabled={aiDisabled || manualLoading}
            onChange={(event) => {
              const selectedOption = LLM_EDIT_REASONING_OPTIONS.find(
                (option) => option.value === event.currentTarget.value,
              );
              if (!selectedOption) {
                console.error('Invalid AI thinking level selected:', event.currentTarget.value);
                return;
              }
              onReasoningChange(selectedOption.value);
            }}
            className="h-8 w-full cursor-pointer appearance-none rounded-full border border-white/70 bg-white/95 px-6 py-0 text-center text-xs font-semibold lowercase text-[#c62828] shadow-sm outline-none transition-all duration-150 hover:bg-white focus:ring-2 focus:ring-white focus:ring-offset-2 focus:ring-offset-[#f44336] disabled:cursor-not-allowed disabled:opacity-50"
          >
            <optgroup label="Thinking level">
              {LLM_EDIT_REASONING_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.value}
                </option>
              ))}
            </optgroup>
          </select>
          <ChevronDown
            aria-hidden="true"
            size={13}
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-[#c62828]"
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
