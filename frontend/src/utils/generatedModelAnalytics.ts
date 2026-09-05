import posthog from 'posthog-js';

export function trackGeneratedModelAiEditClick(
  generationId: string | null,
  isDemoModel: boolean,
  llmModel: string,
): void {
  posthog.capture('generated_model_ai_edit_button_clicked', {
    generation_id: generationId,
    is_demo_model: isDemoModel,
    llm_model: llmModel,
  });
}

export function trackGeneratedModelAiEditModelSelected(
  generationId: string | null,
  llmModel: string,
): void {
  posthog.capture('generated_model_ai_edit_model_selected', {
    generation_id: generationId,
    llm_model: llmModel,
  });
}
