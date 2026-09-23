import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

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

describe('LandingPage', () => {
  it('uses the updated hero headline', () => {
    const markup = renderToStaticMarkup(<LandingPage />);

    expect(markup).toContain('Imagine. Create. Build.');
    expect(markup).not.toContain('Create and Build');
  });

  it('defaults to LLM Render with Claude Opus 5.5, and SAM3D for 3D Render', () => {
    expect(DEFAULT_GENERATION_METHOD).toBe('llm');
    expect(DEFAULT_THREE_D_MODEL).toBe('sam3d');
    expect(DEFAULT_LLM_MODEL).toBe('claude-opus-5-5');

    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="3d" onChange={() => undefined} />,
    );
    expect(markup).toContain('3D Render');
    expect(markup).toContain('LLM Render');
    expect(markup).toMatch(/<option value="sam3d" selected="">SAM3D<\/option>/);
    expect(markup).toContain('<option value="trellis">Trellis</option>');
  });

  it('offers SAM3D and Trellis for 3D Render', () => {
    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="3d" threeDModel="trellis" onChange={() => undefined} />,
    );

    expect(markup).toContain('Generation method:');
    expect(markup).toContain('3D model:');
    expect(markup).toMatch(/<option value="trellis" selected="">Trellis<\/option>/);
    expect(markup).not.toContain('Claude Opus 5.5');
  });

  it('offers grouped Claude and OpenAI models for LLM Render, defaulting to Opus 5.5', () => {
    const markup = renderToStaticMarkup(
      <GenerationMethodSelector value="llm" onChange={() => undefined} />,
    );

    expect(markup).toContain('LLM model:');
    expect(markup).toContain('<optgroup label="Claude">');
    expect(markup).toContain('<optgroup label="OpenAI">');
    expect(markup).toMatch(/<option value="claude-opus-5-5" selected="">Claude Opus 5.5<\/option>/);
    expect(markup).toContain('<option value="gpt-5.6-sol">GPT-5.6 Sol</option>');
    expect(markup).not.toContain('SAM3D');
    expect(markup).toMatch(/aria-pressed="true"[^>]*>LLM Render/);
  });
});
