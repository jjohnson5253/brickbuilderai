import { beforeEach, describe, expect, it, vi } from 'vitest';

import posthog from 'posthog-js';
import { trackGeneratedModelAiEditClick } from '../src/utils/generatedModelAnalytics';

vi.mock('posthog-js', () => ({
  default: {
    capture: vi.fn(),
  },
}));

describe('generated model analytics', () => {
  beforeEach(() => {
    vi.mocked(posthog.capture).mockClear();
  });

  it('captures an event when the AI edit button is pressed', () => {
    trackGeneratedModelAiEditClick('generation-123', false);

    expect(posthog.capture).toHaveBeenCalledWith(
      'generated_model_ai_edit_button_clicked',
      {
        generation_id: 'generation-123',
        is_demo_model: false,
      },
    );
  });
});
