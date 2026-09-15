import posthog from 'posthog-js';

import type { LlmEditReasoningLevel } from './llmEditReasoning';

export function trackGeneratedModelAiEditClick(
  generationId: string | null,
  isDemoModel: boolean,
): void {
  posthog.capture('generated_model_ai_edit_button_clicked', {
    generation_id: generationId,
    is_demo_model: isDemoModel,
  });
}

export function trackGeneratedModelAiReasoningSelected(
  generationId: string | null,
  isDemoModel: boolean,
  reasoningLevel: LlmEditReasoningLevel,
): void {
  posthog.capture('generated_model_ai_reasoning_selected', {
    generation_id: generationId,
    is_demo_model: isDemoModel,
    reasoning_level: reasoningLevel,
  });
}
