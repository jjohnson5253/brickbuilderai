import React from 'react';

interface LlmDesignNotesProps {
  notes: string;
}

export function LlmDesignNotes({ notes }: LlmDesignNotesProps) {
  const notesContainerRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    if (notesContainerRef.current) {
      notesContainerRef.current.scrollTop = notesContainerRef.current.scrollHeight;
    }
  }, [notes]);

  if (!notes) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      className="w-full max-w-sm rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm text-slate-700 shadow-sm sm:max-w-md"
    >
      <p className="mb-1 font-semibold text-slate-900">AI output</p>
      <div
        ref={notesContainerRef}
        className="max-h-48 overflow-y-auto rounded-md border border-slate-200 bg-white px-3 py-2"
      >
        <p className="whitespace-pre-wrap break-words">{notes}</p>
      </div>
    </div>
  );
}
