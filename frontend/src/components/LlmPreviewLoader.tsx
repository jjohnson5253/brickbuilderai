import React from 'react';

const LOADER_BLOCKS = [
  { x: '8%', y: '18%', delay: '0s', duration: '5.6s' },
  { x: '22%', y: '54%', delay: '-0.8s', duration: '6.2s' },
  { x: '38%', y: '26%', delay: '-1.7s', duration: '5.1s' },
  { x: '56%', y: '62%', delay: '-2.4s', duration: '6.8s' },
  { x: '72%', y: '20%', delay: '-1.2s', duration: '5.8s' },
  { x: '84%', y: '50%', delay: '-3.1s', duration: '6.4s' },
] as const;

export function LlmPreviewLoader({ previewImageUrl, compact = false }: { previewImageUrl?: string | null; compact?: boolean }) {
  return (
    <div className="llm-preview-loader" style={compact ? { height: '100%' } : undefined}>
      <div className="llm-preview-loader-glow" />
      <div className="llm-preview-loader-grid" />
      <div className="llm-preview-loader-orbit" aria-hidden="true">
        {LOADER_BLOCKS.map((block, index) => (
          <span
            key={`${block.x}-${block.y}-${index}`}
            className="llm-preview-loader-block"
            style={{
              left: block.x,
              top: block.y,
              animationDelay: block.delay,
              animationDuration: block.duration,
            }}
          >
            <span className="llm-preview-loader-block-face llm-preview-loader-block-face-top" />
            <span className="llm-preview-loader-block-face llm-preview-loader-block-face-front" />
            <span className="llm-preview-loader-block-face llm-preview-loader-block-face-side" />
          </span>
        ))}
      </div>
      <div className="absolute inset-0 flex items-center justify-center px-6">
        {previewImageUrl ? (
          <div className="llm-preview-loader-image-shell">
            <img
              src={previewImageUrl}
              alt="Generation preview"
              className="h-full w-full object-contain"
            />
          </div>
        ) : !compact ? (
          <div className="pointer-events-none rounded-full border border-white/15 bg-slate-950/45 px-4 py-2 text-center text-xs font-medium tracking-[0.24em] text-slate-100 uppercase shadow-lg backdrop-blur-md sm:text-sm">
            BrickBuilder AI is sketching your build
          </div>
        ) : null}
      </div>
    </div>
  );
}
