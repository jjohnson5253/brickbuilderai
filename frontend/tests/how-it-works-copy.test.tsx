import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import { HowItWorksSection } from '../src/components/HowItWorksSection';

describe('landing page how it works copy', () => {
  it('includes a child-friendly GitHub learn-more message', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      act(() => {
        root.render(<HowItWorksSection />);
      });

      expect(container.textContent).toContain('Want to learn the magic?');
      expect(container.textContent).toContain(
        'try running it yourself by exploring the code on',
      );

      const githubLink = Array.from(container.querySelectorAll('a')).find(
        (link) => link.textContent === 'GitHub',
      );
      expect(githubLink).not.toBeNull();
      expect(githubLink?.textContent).toBe('GitHub');
      expect(githubLink?.getAttribute('href')).toBe(
        'https://github.com/jjohnson5253/brickbuilderai',
      );
      expect(githubLink?.getAttribute('target')).toBe('_blank');
      expect(githubLink?.getAttribute('aria-label')).toBe(
        'GitHub (opens in a new tab)',
      );
      expect(githubLink?.getAttribute('rel')).toContain('noopener');
      expect(githubLink?.getAttribute('rel')).toContain('noreferrer');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });
});
