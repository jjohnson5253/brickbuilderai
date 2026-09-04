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
  reference_image_url?: string;
  reference_image_urls?: string[];
  prompt?: string;
  max_segments?: number;
  check_segmentation?: boolean;
}

export interface LlmRenderAppliedRule {
  segment_id: number;
  name: string;
  reason: string | null;
  color: [number, number, number];
  changed_voxels: number;
}

export interface LlmRenderSegmentationAdjustment {
  action: 'merge' | 'split';
  segment_ids?: number[];
  into?: number;
  segment_id?: number;
  pieces?: number;
  new_segment_ids?: number[];
  reason?: string | null;
}

export interface LlmRenderResponse {
  xyzrgb_content: string;
  voxel_count: number;
  segment_count: number;
  model: string;
  applied_rules: LlmRenderAppliedRule[];
  segmentation_adjustments?: LlmRenderSegmentationAdjustment[];
  preview_image?: string | null;
  message: string;
}

export class LlmRenderApiService {
  static async llmRender(
    xyzrgbUrl: string,
    referenceImageUrls: string | string[],
    prompt?: string,
    accessToken?: string
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
      reference_image_urls: Array.isArray(referenceImageUrls)
        ? referenceImageUrls
        : [referenceImageUrls],
      prompt,
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
}
