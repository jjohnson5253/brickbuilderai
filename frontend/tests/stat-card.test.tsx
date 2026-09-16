import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';

import { StatCard } from '../src/components/StatCard';

describe('StatCard', () => {
  it('renders as an interactive card and invokes its action', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const onClick = vi.fn();

    try {
      act(() => {
        root.render(
          <StatCard
            icon={<span>Icon</span>}
            title="123 Pieces"
            sub=""
            actionLabel="View building instructions"
            onClick={onClick}
          />,
        );
      });

      const action = container.querySelector(
        '[aria-label="View building instructions"]',
      ) as HTMLButtonElement;
      expect(action).not.toBeNull();
      expect(action.className).toContain('hover:border-[#f44336]');

      act(() => {
        action.click();
      });
      expect(onClick).toHaveBeenCalledOnce();
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });
});
