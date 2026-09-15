import { describe, expect, it } from 'vitest';

import {
  DEFAULT_LLM_EDIT_REASONING_LEVEL,
  getLlmEditMaxSegmentationRounds,
} from '../src/utils/llmEditReasoning';

describe('LLM edit reasoning', () => {
  it('defaults AI edits to low reasoning', () => {
    expect(DEFAULT_LLM_EDIT_REASONING_LEVEL).toBe('low');
    expect(getLlmEditMaxSegmentationRounds(DEFAULT_LLM_EDIT_REASONING_LEVEL)).toBe(1);
  });
});
