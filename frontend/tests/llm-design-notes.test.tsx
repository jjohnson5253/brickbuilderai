import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { LlmDesignNotes } from '../src/components/LlmDesignNotes';

describe('LlmDesignNotes', () => {
  it('keeps completed design notes visible without an editing-state dependency', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes="Use red bricks for the torso." />,
    );

    expect(markup).toContain('AI output');
    expect(markup).toContain('Use red bricks for the torso.');
    expect(markup).toContain('max-h-48');
    expect(markup).toContain('overflow-y-auto');
  });

  it('renders nothing before design notes arrive', () => {
    expect(renderToStaticMarkup(<LlmDesignNotes notes="" />)).toBe('');
  });
});
