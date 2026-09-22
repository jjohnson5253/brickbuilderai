export interface ClaudeToBricksRequest {
  prompt?: string;
  imageBase64?: string;
  imageMediaType?: string;
  detailLevel?: number;
}

export interface ClaudeToBricksResponse {
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

export class ClaudeToBricksApiService {
  static async generate(
    request: ClaudeToBricksRequest,
    authToken?: string,
  ): Promise<ClaudeToBricksResponse> {
    const prompt = request.prompt?.trim();
    if (!prompt && !request.imageBase64) {
      throw new Error('A prompt or image is required');
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (authToken) headers.Authorization = `Bearer ${authToken}`;

    const response = await fetch(`${API_BASE_URL}/claudeToBricks`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        prompt: prompt || undefined,
        image_base64: request.imageBase64,
        image_media_type: request.imageMediaType || 'image/png',
        detail_level: request.detailLevel ?? 40,
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      let errorMessage = 'Failed to generate an LDraw model with Claude';
      try {
        const errorData = JSON.parse(errorText);
        errorMessage = errorData.error || errorData.detail || errorMessage;
      } catch {
        errorMessage = errorText || `${response.status} ${response.statusText}`;
      }
      throw new Error(errorMessage);
    }

    const responseData: ClaudeToBricksResponse = await response.json();
    if (!responseData.generation_id) {
      throw new Error('Invalid response from server: missing generation_id');
    }
    return responseData;
  }
}
