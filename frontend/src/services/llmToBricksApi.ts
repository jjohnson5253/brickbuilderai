export type LlmProvider = 'anthropic' | 'openai';

export interface LlmModelOption {
  id: string;
  label: string;
  provider: LlmProvider;
}

// Must match SUPPORTED_MODELS in backend/src/requests/llmToBricks.py; the
// backend rejects any other model id.
export const LLM_MODEL_OPTIONS: readonly LlmModelOption[] = [
  { id: 'claude-opus-5-5', label: 'Claude Opus 5.5', provider: 'anthropic' },
  { id: 'claude-opus-5', label: 'Claude Opus 5', provider: 'anthropic' },
  { id: 'claude-sonnet-5', label: 'Claude Sonnet 5', provider: 'anthropic' },
  { id: 'claude-fable-5', label: 'Claude Fable 5', provider: 'anthropic' },
  { id: 'gpt-5.6-sol', label: 'GPT-5.6 Sol', provider: 'openai' },
  { id: 'gpt-5.6-terra', label: 'GPT-5.6 Terra', provider: 'openai' },
  { id: 'gpt-5.5', label: 'GPT-5.5', provider: 'openai' },
];

export const DEFAULT_LLM_MODEL = 'claude-opus-5-5';

export function getLlmModelOption(id: string): LlmModelOption | undefined {
  return LLM_MODEL_OPTIONS.find((option) => option.id === id);
}

export interface LlmToBricksRequest {
  prompt?: string;
  imageBase64?: string;
  imageMediaType?: string;
  detailLevel?: number;
  model?: string;
}

export interface LlmToBricksResponse {
  generation_id: string;
  message: string;
}

const API_MODE = import.meta.env.VITE_API_MODE || 'local';
const LOCAL_API_URL = import.meta.env.VITE_LOCAL_API_URL || 'http://127.0.0.1:8002';
const RAILWAY_API_URL = import.meta.env.VITE_RAILWAY_API_URL || 'https://brickai-backend-production.up.railway.app';
const RAILWAY_API_URL_STAGING = import.meta.env.VITE_RAILWAY_API_URL_STAGING || 'https://brickai-backend-staging.up.railway.app';

const API_BASE_URL = API_MODE === 'local'
  ? LOCAL_API_URL
  : API_MODE === 'railway_staging'
    ? RAILWAY_API_URL_STAGING
    : RAILWAY_API_URL;

export class LlmToBricksApiService {
  static async generate(
    request: LlmToBricksRequest,
    authToken?: string,
  ): Promise<LlmToBricksResponse> {
    const prompt = request.prompt?.trim();
    if (!prompt && !request.imageBase64) {
      throw new Error('A prompt or image is required');
    }
    const model = request.model ?? DEFAULT_LLM_MODEL;
    if (!getLlmModelOption(model)) {
      throw new Error(`Unsupported model: ${model}`);
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authToken) headers.Authorization = 'Bearer ' + authToken;

    const response = await fetch(`${API_BASE_URL}/llmToBricks`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        prompt: prompt || undefined,
        image_base64: request.imageBase64,
        image_media_type: request.imageMediaType || 'image/png',
        detail_level: request.detailLevel ?? 40,
        model,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = 'Failed to generate a brick model with the LLM';
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.error || errorData.detail || errorMessage;
      } catch {
        errorMessage = errorText || `${response.status} ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const responseData: LlmToBricksResponse = await response.json();
    if (!responseData.generation_id) {
      throw new Error('Invalid response from server: missing generation_id');
    }
    return responseData;
  }
}
