// API Configuration
const API_MODE = import.meta.env.VITE_API_MODE || 'local';
const LOCAL_API_URL = import.meta.env.VITE_LOCAL_API_URL || 'http://127.0.0.1:8002';
const RAILWAY_API_URL = import.meta.env.VITE_RAILWAY_API_URL || 'https://brickai-backend-production.up.railway.app';
const RAILWAY_API_URL_STAGING = import.meta.env.VITE_RAILWAY_API_URL_STAGING || 'https://brickai-backend-staging.up.railway.app';

const getApiUrl = () => {
  if (API_MODE === 'local') {
    return LOCAL_API_URL;
  } else if (API_MODE === 'railway_staging') {
    return RAILWAY_API_URL_STAGING;
  } else {
    return RAILWAY_API_URL;
  }
};

const API_BASE_URL = getApiUrl();

export interface LlmRenderRequest {
  xyzrgb_url: string;
  reference_image_url: string;
  prompt?: string;
  model?: string;
  max_segments?: number;
}

export interface LlmEditModelOption {
  id: string;
  label: string;
  provider: 'openai' | 'anthropic';
}

// Models users can pick for AI editing. Must stay in sync with
// SUPPORTED_LLM_MODELS in backend/src/requests/llmRender.py.
export const LLM_EDIT_MODELS: LlmEditModelOption[] = [
  { id: 'gpt-5.6-sol', label: 'GPT-5.6 Sol (OpenAI)', provider: 'openai' },
  { id: 'gpt-5.1', label: 'GPT-5.1 (OpenAI)', provider: 'openai' },
  { id: 'claude-fable', label: 'Claude Fable (Anthropic)', provider: 'anthropic' },
  { id: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5 (Anthropic)', provider: 'anthropic' },
];

export const DEFAULT_LLM_EDIT_MODEL_ID = LLM_EDIT_MODELS[0].id;

export interface LlmRenderAppliedRule {
  segment_id: number;
  name: string;
  reason: string | null;
  color: [number, number, number];
  changed_voxels: number;
}

export interface LlmRenderResponse {
  xyzrgb_content: string;
  voxel_count: number;
  segment_count: number;
  model: string;
  applied_rules: LlmRenderAppliedRule[];
  preview_image?: string | null;
  message: string;
}

export class LlmRenderApiService {
  static async llmRender(
    xyzrgbUrl: string,
    referenceImageUrl: string,
    prompt?: string,
    accessToken?: string,
    model?: string
  ): Promise<LlmRenderResponse> {
    const url = `${API_BASE_URL}/llmRender`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    if (accessToken) {
      headers.Authorization = `Bearer ${accessToken}`;
    }

    const requestBody: LlmRenderRequest = {
      xyzrgb_url: xyzrgbUrl,
      reference_image_url: referenceImageUrl,
      prompt,
      ...(model ? { model } : {}),
    };

    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed: ${response.status} ${response.statusText}. ${errorText}`);
    }

    const data: LlmRenderResponse = await response.json();
    if (!data.xyzrgb_content) {
      throw new Error('Invalid response structure from llmRender API');
    }

    return data;
  }

  static async llmRenderStream(
    xyzrgbUrl: string,
    referenceImageUrl: string,
    prompt?: string,
    accessToken?: string,
    onThinking?: (delta: string) => void,
    model?: string,
  ): Promise<LlmRenderResponse> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (accessToken) {
      headers.Authorization = 'Bearer ' + accessToken;
    }

    const response = await fetch(`${API_BASE_URL}/llmRender/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        xyzrgb_url: xyzrgbUrl,
        reference_image_url: referenceImageUrl,
        prompt,
        ...(model ? { model } : {}),
      } satisfies LlmRenderRequest),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`API request failed: ${response.status} ${response.statusText}. ${errorText}`);
    }
    if (!response.body) {
      throw new Error('Response body is null — streaming not supported by browser');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let result: LlmRenderResponse | undefined;

    while (true) {
      const { done, value } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });

      while (buffer.includes('\n\n')) {
        const delimiterIndex = buffer.indexOf('\n\n');
        const rawEvent = buffer.slice(0, delimiterIndex);
        buffer = buffer.slice(delimiterIndex + 2);
        if (!rawEvent.startsWith('data: ')) continue;

        const event = JSON.parse(rawEvent.slice(6)) as
          | { type: 'thinking'; delta: string }
          | { type: 'result'; data: LlmRenderResponse }
          | { type: 'error'; detail: string };
        if (event.type === 'thinking') {
          onThinking?.(event.delta);
        } else if (event.type === 'result') {
          result = event.data;
        } else if (event.type === 'error') {
          throw new Error(event.detail);
        }
      }

      if (done) break;
    }

    if (!result?.xyzrgb_content) {
      throw new Error('LLM render stream ended without a result');
    }
    return result;
  }
}
