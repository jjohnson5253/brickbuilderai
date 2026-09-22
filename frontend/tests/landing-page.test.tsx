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

import LandingPage, {
  FEATURED_STRIP_DRAG_THRESHOLD_PX,
  getFeaturedStripGestureDirection,
} from '../src/pages/LandingPage';

describe('LandingPage', () => {
  it('uses the updated hero headline', () => {
    const markup = renderToStaticMarkup(<LandingPage />);

    expect(markup).toContain('Imagine. Create. Build.');
    expect(markup).not.toContain('Create and Build');
  });

  it('allows vertical panning on the featured carousel track', () => {
    const markup = renderToStaticMarkup(<LandingPage />);

    expect(markup).toContain('touch-action:pan-y');
  });

  it('waits for a meaningful gesture before dragging the featured carousel', () => {
    expect(
      getFeaturedStripGestureDirection(
        FEATURED_STRIP_DRAG_THRESHOLD_PX - 1,
        FEATURED_STRIP_DRAG_THRESHOLD_PX - 1,
      ),
    ).toBe('undecided');
  });

  it('locks the featured carousel to the dominant gesture direction', () => {
    expect(getFeaturedStripGestureDirection(24, 8)).toBe('horizontal');
    expect(getFeaturedStripGestureDirection(8, 24)).toBe('vertical');
    expect(getFeaturedStripGestureDirection(12, 12)).toBe('vertical');
  });
});
