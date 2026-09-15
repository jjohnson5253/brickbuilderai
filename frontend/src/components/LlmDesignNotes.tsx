import React from 'react';

interface LlmDesignNotesProps {
  notes: string;
  isThinking?: boolean;
}

export function LlmDesignNotes({ notes, isThinking = false }: LlmDesignNotesProps) {
  const hasNotes = notes.trim().length > 0;

  if (!hasNotes && !isThinking) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      className="w-full max-w-sm rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm text-slate-700 shadow-sm sm:max-w-md"
    >
      {hasNotes ? (
        <p className="whitespace-pre-wrap break-words">{notes}</p>
      ) : (
        <div className="flex items-center gap-2 text-slate-900">
          <span className="font-semibold">Brickbuilder AI thinking</span>
          <span aria-hidden="true" className="inline-flex items-center gap-1">
            <span className="thinking-dot" />
            <span className="thinking-dot thinking-dot-delay-1" />
            <span className="thinking-dot thinking-dot-delay-2" />
          </span>
        </div>
      )}
    </div>
  );
}
