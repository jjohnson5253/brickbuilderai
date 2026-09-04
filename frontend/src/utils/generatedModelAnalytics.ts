import posthog from 'posthog-js';

export function trackGeneratedModelAiEditClick(
  generationId: string | null,
  isDemoModel: boolean,
): void {
  posthog.capture('generated_model_ai_edit_button_clicked', {
    generation_id: generationId,
    is_demo_model: isDemoModel,
  });
}
