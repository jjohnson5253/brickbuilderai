import React from 'react';

interface LlmDesignNotesProps {
  notes: string;
  isThinking?: boolean;
}

const SEGMENTATION_STATUS_PATTERN = /(Checking segmentation(?: \(round \d+\/\d+\))?\.\.\.)/gi;

function renderNotes(notes: string, isThinking: boolean) {
  const parts = notes.split(SEGMENTATION_STATUS_PATTERN);

  return parts.map((part, index) => {
    if (!/^Checking segmentation(?: \(round \d+\/\d+\))?\.\.\.$/i.test(part)) {
      return part;
    }

    const hasLaterOutput = parts.slice(index + 1).some((laterPart) => laterPart.trim().length > 0);
    if (!isThinking || hasLaterOutput) return part;

    return (
      <span key={`${part}-${index}`} aria-label={part}>
        <span aria-hidden="true" className="inline-flex items-baseline">
          {part.slice(0, -3)}
          <span className="ml-1 inline-flex items-center gap-0.5">
            <span className="thinking-sequential-dot" />
            <span className="thinking-sequential-dot thinking-sequential-dot-2" />
            <span className="thinking-sequential-dot thinking-sequential-dot-3" />
          </span>
        </span>
      </span>
    );
  });
}

export function LlmDesignNotes({ notes, isThinking = false }: LlmDesignNotesProps) {
  const notesContainerRef = React.useRef<HTMLDivElement | null>(null);
  const hasNotes = notes.trim().length > 0;

  React.useEffect(() => {
    if (notesContainerRef.current) {
      notesContainerRef.current.scrollTop = notesContainerRef.current.scrollHeight;
    }
  }, [notes]);

  if (!hasNotes && !isThinking) {
    return null;
  }

  return (
    <div
      aria-live="polite"
      className="w-full max-w-sm rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-sm text-slate-700 shadow-sm sm:max-w-md"
    >
      {hasNotes ? (
        <>
          <p className="mb-1 font-semibold text-slate-900">Brickbuilder AI Output</p>
          <div
            ref={notesContainerRef}
            className="max-h-48 overflow-y-auto rounded-md border border-slate-200 bg-white px-3 py-2"
          >
            <p className="whitespace-pre-wrap break-words">{renderNotes(notes, isThinking)}</p>          </div>
        </>
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
