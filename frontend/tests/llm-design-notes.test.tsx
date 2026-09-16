import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import { LlmDesignNotes } from '../src/components/LlmDesignNotes';

describe('LlmDesignNotes', () => {
  it('keeps completed design notes visible without an editing-state dependency', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes="Use red bricks for the torso." />,
    );

    expect(markup).toContain('Use red bricks for the torso.');
    expect(markup).toContain('Brickbuilder AI Output');
    expect(markup).toContain('max-h-48');
    expect(markup).toContain('overflow-y-auto');
    expect(markup).not.toContain('Brickbuilder AI thinking');
  });

  it('renders nothing before design notes arrive', () => {
    expect(renderToStaticMarkup(<LlmDesignNotes notes="" />)).toBe('');
  });

  it('auto-scrolls to the latest streamed output', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const scrollHeightSpy = vi.spyOn(HTMLElement.prototype, 'scrollHeight', 'get').mockReturnValue(320);

    try {
      act(() => {
        root.render(<LlmDesignNotes notes={'Line 1\nLine 2'} />);
      });

      const scroller = container.querySelector('.overflow-y-auto') as HTMLDivElement | null;
      expect(scroller).not.toBeNull();
      expect(scroller?.scrollTop).toBe(320);
    } finally {
      scrollHeightSpy.mockRestore();
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  it('shows the Brickbuilder AI thinking state until streamed notes arrive', () => {
    const markup = renderToStaticMarkup(<LlmDesignNotes notes="" isThinking />);

    expect(markup).toContain('Brickbuilder AI thinking');
    expect(markup).toContain('thinking-dot');
  });

  it('hides the thinking state when streamed notes arrive', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes="The torso should use red bricks." isThinking />,
    );

    expect(markup).toContain('The torso should use red bricks.');
    expect(markup).not.toContain('Brickbuilder AI thinking');
  });

  it('animates the ellipsis while segmentation is the active status', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes="Checking segmentation (round 1/3)..." isThinking />,
    );

    expect(markup).toContain('aria-label="Checking segmentation (round 1/3)..."');
    expect(markup).toContain('thinking-sequential-dot');
  });

  it('stops animating segmentation dots when later output arrives', () => {
    const markup = renderToStaticMarkup(
      <LlmDesignNotes notes={'Checking segmentation (round 1/3)...\nApplying colors'} isThinking />,
    );

    expect(markup).toContain('Checking segmentation (round 1/3)...');
    expect(markup).toContain('Applying colors');
    expect(markup).not.toContain('thinking-sequential-dot');
  });
});
