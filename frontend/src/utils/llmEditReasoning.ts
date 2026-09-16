export type LlmEditReasoningLevel = 'low' | 'medium' | 'high';

export const DEFAULT_LLM_EDIT_REASONING_LEVEL: LlmEditReasoningLevel = 'low';

export const LLM_EDIT_REASONING_OPTIONS: Array<{
  label: string;
  value: LlmEditReasoningLevel;
  maxSegmentationRounds: number;
}> = [
  { label: 'Low', value: 'low', maxSegmentationRounds: 1 },
  { label: 'Medium', value: 'medium', maxSegmentationRounds: 2 },
  { label: 'High', value: 'high', maxSegmentationRounds: 3 },
];

export function getLlmEditMaxSegmentationRounds(level: LlmEditReasoningLevel): number {
  return LLM_EDIT_REASONING_OPTIONS.find((option) => option.value === level)?.maxSegmentationRounds ?? 3;
}
