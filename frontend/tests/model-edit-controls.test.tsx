import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';

import { ModelEditControls } from '../src/components/ModelEditControls';

describe('ModelEditControls', () => {
  it('renders AI Edit with an embedded thinking-level pill and manual edit', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      act(() => {
        root.render(
          <ModelEditControls
            aiDisabled={false}
            isAiEditing={false}
            isManualEditorOpen={false}
            manualLoading={false}
            reasoningLevel="low"
            onAiEdit={vi.fn()}
            onManualEdit={vi.fn()}
            onReasoningChange={vi.fn()}
          />,
        );
      });

      expect(container.textContent).toContain('AI Edit');
      expect(container.textContent).toContain('Manual Edit');
      expect(
        (container.querySelector('[aria-label="Thinking level"]') as HTMLSelectElement).value,
      ).toBe('low');
      expect(container.querySelector('optgroup')?.label).toBe('Thinking level');
      expect(
        Array.from(container.querySelectorAll('option')).map((option) => option.textContent),
      ).toEqual(['low', 'medium', 'high']);
      expect(
        container.querySelector('[aria-label="Thinking level"]')?.parentElement?.className,
      ).toContain('w-24');
      expect(
        container.querySelector('[aria-label="Thinking level"]')?.parentElement?.className,
      ).toContain('absolute');
      expect(
        container.querySelector('[aria-label="Thinking level"]')?.className,
      ).toContain('rounded-full');
      expect(
        container.querySelector('[aria-label="Thinking level"]')?.className,
      ).toContain('h-8');
      expect(
        container.querySelector('[aria-label="Thinking level"]')?.className,
      ).toContain('text-center');
      expect(
        container.querySelector('[aria-label="AI edit model"]')?.parentElement?.className,
      ).toContain('attention-pulse');
      expect(
        container.querySelector('[aria-label="AI edit model"]')?.className,
      ).toContain('rounded-full');
      expect(container.firstElementChild?.className).toContain('sm:flex-row');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });

  it('reports thinking level changes', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const onReasoningChange = vi.fn();

    try {
      act(() => {
        root.render(
          <ModelEditControls
            aiDisabled={false}
            isAiEditing={false}
            isManualEditorOpen={false}
            manualLoading={false}
            reasoningLevel="low"
            onAiEdit={vi.fn()}
            onManualEdit={vi.fn()}
            onReasoningChange={onReasoningChange}
          />,
        );
      });

      const selector = container.querySelector(
        '[aria-label="Thinking level"]',
      ) as HTMLSelectElement;
      act(() => {
        selector.value = 'high';
        selector.dispatchEvent(new Event('change', { bubbles: true }));
      });

      expect(onReasoningChange).toHaveBeenCalledOnce();
      expect(onReasoningChange).toHaveBeenCalledWith('high');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });
});
