import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { LlmDesignNotes } from '../src/components/LlmDesignNotes';

describe('LlmDesignNotes', () => {
  it('keeps completed design notes visible without an editing-state dependency', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes="Use red bricks for the torso." />,
    );

    expect(markup).toContain('Use red bricks for the torso.');
    expect(markup).not.toContain('Brickbuilder AI thinking');
  });

  it('renders nothing before design notes arrive', () => {
    expect(renderToStaticMarkup(<LlmDesignNotes notes="" />)).toBe('');
  });

  it('shows the Brickbuilder AI thinking state until streamed notes arrive', () => {
    const markup = renderToStaticMarkup(<LlmDesignNotes notes="" isThinking />);

    expect(markup).toContain('Brickbuilder AI thinking');
    expect(markup).toContain('thinking-dot');
  });
});
