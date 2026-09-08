import React from 'react';

interface LlmDesignNotesProps {
  notes: string;
}

export function LlmDesignNotes({ notes }: LlmDesignNotesProps) {
  if (!notes) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      className="w-full max-w-sm rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm text-slate-700 shadow-sm sm:max-w-md"
    >
      <p className="mb-1 font-semibold text-slate-900">AI output</p>
      <p className="whitespace-pre-wrap break-words">{notes}</p>
    </div>
  );
}
