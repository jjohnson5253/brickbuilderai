import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { LlmPreviewLoader } from '../src/components/LlmPreviewLoader';

describe('LlmPreviewLoader', () => {
  it('fits compact activity cards without clipping the loading copy', () => {
    const markup = renderToStaticMarkup(<LlmPreviewLoader compact />);
    expect(markup).toContain('height:100%');
    expect(markup).toContain('llm-preview-loader-block');
    expect(markup).not.toContain('BrickBuilder AI is sketching your build');
  });

  it('renders the animated block scene and loading copy without a preview image', () => {
    const markup = renderToStaticMarkup(<LlmPreviewLoader />);

    expect(markup).toContain('llm-preview-loader');
    expect(markup).toContain('llm-preview-loader-block');
    expect(markup).toContain('BrickBuilder AI is sketching your build');
    expect(markup).not.toContain('Generation preview');
  });

  it('renders the preview image inside the animated shell when one is available', () => {
    const markup = renderToStaticMarkup(
      <LlmPreviewLoader previewImageUrl="https://example.com/preview.png" />,
    );

    expect(markup).toContain('llm-preview-loader-image-shell');
    expect(markup).toContain('src="https://example.com/preview.png"');
    expect(markup).toContain('alt="Generation preview"');
  });
});
