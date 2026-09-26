import React from 'react';
import { createRoot } from 'react-dom/client';
import { renderToStaticMarkup } from 'react-dom/server';
import { act } from 'react-dom/test-utils';
import { describe, expect, it, vi } from 'vitest';

vi.mock('posthog-js', () => ({
  default: {
    capture: vi.fn(),
  },
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');

  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock('../src/contexts/AuthContext', () => ({
  useAuth: () => ({
    session: null,
    loading: false,
    user: null,
    isSupabaseConfigured: false,
  }),
}));

vi.mock('../src/components/SEO', () => ({
  SEO: () => null,
}));

vi.mock('../src/components/FallingBricks', () => ({
  default: () => null,
}));

vi.mock('../src/components/LoginModal', () => ({
  default: () => null,
}));

vi.mock('../src/components/StreamingMeshViewer', () => ({
  default: () => null,
}));

vi.mock('../src/components/SiteFooter', () => ({
  SiteFooter: () => null,
}));

vi.mock('../src/components/GlbUploadCard', () => ({
  GlbUploadCard: () => null,
}));

vi.mock('../src/components/ProfileMenu', () => ({
  ProfileMenu: () => null,
}));

import LandingPage, { DEFAULT_GENERATION_METHOD, DEFAULT_THREE_D_MODEL, GenerationMethodSelector } from '../src/pages/LandingPage';
import { DEFAULT_LLM_MODEL } from '../src/services/llmToBricksApi';
import { LlmToBricksApiService } from '../src/services/llmToBricksApi';
import { GetUserGenerationsApiService } from '../src/services/getUserGenerationsApi';
import { GetGenerationStatsApiService } from '../src/services/getGenerationStatsApi';
import { GetGenerationApiService } from '../src/services/getGenerationApi';

describe('LandingPage', () => {
  it('starts LLM jobs in the background and allows another submission while they run', async () => {
    vi.spyOn(GetUserGenerationsApiService, 'getProcessingGenerations').mockResolvedValue([]);
    vi.spyOn(GetGenerationStatsApiService, 'getGenerationStats').mockResolvedValue({ generation_count: 12, brick_count: 400 });
    const start = vi.spyOn(LlmToBricksApiService, 'generate')
      .mockResolvedValueOnce({ generation_id: 'one', message: 'Started' })
      .mockResolvedValueOnce({ generation_id: 'two', message: 'Started' });
    const stream = vi.spyOn(LlmToBricksApiService, 'generateStream');
    const poll = vi.spyOn(GetGenerationApiService, 'pollUntilComplete');
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    try {
      await act(async () => root.render(<LandingPage />));
      await act(async () => Array.from(container.querySelectorAll('button')).find(button => button.textContent?.trim() === 'Generate')!.click());
      expect(start).not.toHaveBeenCalled();
      expect((await import('posthog-js')).default.capture).toHaveBeenCalledWith('landing_generate_clicked', expect.objectContaining({ has_prompt: false, has_image: false }));
      const input = container.querySelector('input:not([type="file"])') as HTMLInputElement;
      act(() => {
        Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'Red castle');
        input.dispatchEvent(new Event('input', { bubbles: true }));
      });
      const generate = () => Array.from(container.querySelectorAll('button')).find(button => button.textContent?.trim() === 'Generate')!;
      await act(async () => generate().click());
      expect(container.textContent).toContain('1 in progress');
      expect(input.disabled).toBe(false);
      await act(async () => generate().click());
      expect(container.querySelectorAll('[aria-label="Your generations"] article')).toHaveLength(2);
      expect(container.textContent).toContain('2 in progress');
      expect(start).toHaveBeenCalledTimes(2);
      expect((await import('posthog-js')).default.capture).toHaveBeenCalledWith('landing_generate_clicked', {
        generation_method: 'llm', model: DEFAULT_LLM_MODEL, has_prompt: true,
        has_image: false, size: 'big', is_authenticated: false,
      });
      expect(stream).not.toHaveBeenCalled();
      expect(poll).not.toHaveBeenCalled();
      expect(JSON.parse(localStorage.getItem('pending_generations:anonymous')!).map((row: { id: string }) => row.id)).toEqual(['two', 'one']);
    } finally {
      act(() => root.unmount());
      container.remove();
    }
  });

  it('uses the updated hero headline', () => {
    const markup = renderToStaticMarkup(<LandingPage />);

    expect(markup).toContain('Imagine. Create. Build.');
    expect(markup).not.toContain('Create and Build');
  });

  it('defaults to LLM Render with Claude Opus 5.5, and SAM3D for image-to-glb', () => {
    expect(DEFAULT_GENERATION_METHOD).toBe('llm');
    expect(DEFAULT_THREE_D_MODEL).toBe('sam3d');
    expect(DEFAULT_LLM_MODEL).toBe('claude-opus-5-5');

    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="3d" onChange={() => undefined} />,
    );
    expect(markup).toContain('image-to-glb:');
    expect(markup).not.toContain('3D Render');
    expect(markup).toContain('LLM Render');
    expect(markup).toMatch(/aria-pressed="true"[^>]*>SAM3D/);
    expect(markup).toContain('Trellis');
  });

  it('offers SAM3D and Trellis for image-to-glb without the old 3D style controls', () => {
    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="3d" threeDModel="trellis" onChange={() => undefined} />,
    );

    expect(markup).toContain('Generation method:');
    expect(markup).toContain('image-to-glb:');
    expect(markup).toMatch(/aria-pressed="true"[^>]*>Trellis/);
    expect(markup).not.toContain('3D model:');
    expect(markup).not.toContain('LLM model:');
  });

  it('offers grouped Claude and OpenAI models for LLM Render, defaulting to Opus 5.5', () => {
    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="llm" onChange={() => undefined} />,
    );

    expect(markup).toContain('LLM model:');
    expect(markup).toContain('image-to-glb:');
    expect(markup).toContain('<optgroup label="Claude">');
    expect(markup).toContain('<optgroup label="OpenAI">');
    expect(markup).toMatch(/<option value="claude-opus-5-5" selected="">Claude Opus 5.5<\/option>/);
    expect(markup).toContain('<option value="gpt-5.6-sol">GPT-5.6 Sol</option>');
    expect(markup).toContain('SAM3D');
    expect(markup).toMatch(/aria-pressed="true"[^>]*>LLM Render/);
  });

  it('reports method changes and model selections through the shared controls', async () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);
    const onChange = vi.fn();
    const onThreeDModelChange = vi.fn();
    const onLlmModelChange = vi.fn();
    const capture = (await import('posthog-js')).default.capture;

    try {
      act(() => {
        root.render(
          <GenerationMethodSelector
            value="llm"
            onChange={onChange}
            onThreeDModelChange={onThreeDModelChange}
            onLlmModelChange={onLlmModelChange}
          />,
        );
      });

      const trellisButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent === 'Trellis',
      );
      act(() => trellisButton?.click());
      expect(onChange).toHaveBeenCalledWith('3d');
      expect(onThreeDModelChange).toHaveBeenCalledWith('trellis');
      expect(capture).toHaveBeenCalledWith('landing_generation_method_selected', {
        generation_method: '3d',
      });
      expect(capture).toHaveBeenCalledWith('landing_render_model_selected', {
        generation_method: '3d',
        model: 'trellis',
        provider: '3d',
      });

      const llmSelect = container.querySelector('select') as HTMLSelectElement;
      act(() => {
        llmSelect.value = 'gpt-5.6-sol';
        llmSelect.dispatchEvent(new Event('change', { bubbles: true }));
      });
      expect(onLlmModelChange).toHaveBeenCalledWith('gpt-5.6-sol');

      act(() => {
        root.render(
          <GenerationMethodSelector
            value="3d"
            threeDModel="sam3d"
            onChange={onChange}
            onThreeDModelChange={onThreeDModelChange}
            onLlmModelChange={onLlmModelChange}
          />,
        );
      });

      onChange.mockClear();
      onThreeDModelChange.mockClear();
      vi.mocked(capture).mockClear();

      const activeThreeDButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent === 'Trellis',
      );
      act(() => {
        activeThreeDButton?.click();
      });
      expect(onChange).not.toHaveBeenCalled();
      expect(onThreeDModelChange).toHaveBeenCalledWith('trellis');
      expect(capture).not.toHaveBeenCalledWith('landing_generation_method_selected', {
        generation_method: '3d',
      });
      expect(capture).toHaveBeenCalledWith('landing_render_model_selected', {
        generation_method: '3d',
        model: 'trellis',
        provider: '3d',
      });

      onChange.mockClear();
      vi.mocked(capture).mockClear();

      const llmButton = Array.from(container.querySelectorAll('button')).find(
        (button) => button.textContent === 'LLM Render',
      );
      act(() => {
        llmButton?.click();
      });
      expect(onChange).toHaveBeenCalledWith('llm');
    } finally {
      act(() => root.unmount());
      container.remove();
    }
  });

  it('expands the shared method and model controls by default in the native shell', () => {
    window.__BRICKBUILDER_NATIVE_APP__ = Object.freeze({
      platform: 'ios',
      version: '0.1.0',
    });

    try {
      const markup = renderToStaticMarkup(<LandingPage />);

      expect(markup).toContain('Generation method:');
      expect(markup).toContain('image-to-glb:');
      expect(markup).not.toContain('3D Render');
      expect(markup).toContain('LLM Render');
      expect(markup).toContain('LLM model:');
      expect(markup).toContain('Claude Opus 5.5');
      expect(markup).toContain('GPT-5.6 Sol');
      expect(markup).not.toContain('Style:');
      expect(markup).not.toContain('Plush');
      expect(markup).not.toContain('Block');
    } finally {
      delete window.__BRICKBUILDER_NATIVE_APP__;
    }
  });
});
