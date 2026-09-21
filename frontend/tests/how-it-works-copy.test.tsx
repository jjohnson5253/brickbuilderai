import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { describe, expect, it } from 'vitest';
import { HowItWorks } from '../src/pages/LandingPage';

describe('landing page how it works copy', () => {
  it('includes a child-friendly GitHub learn-more message', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      act(() => {
        root.render(<HowItWorks />);
      });

      expect(container.textContent).toContain('Want to learn the magic?');
      expect(container.textContent).toContain(
        'try running it yourself by exploring the code on',
      );

      const githubLink = container.querySelector('a[href="https://github.com/jjohnson5253/brickbuilderai"]');
      expect(githubLink).not.toBeNull();
      expect(githubLink?.textContent).toBe('GitHub');
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
