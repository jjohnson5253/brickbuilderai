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

    expect(markup).toContain('AI output');
    expect(markup).toContain('Use red bricks for the torso.');
    expect(markup).toContain('max-h-48');
    expect(markup).toContain('overflow-y-auto');
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
});
