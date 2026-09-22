import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import { describe, expect, it, vi } from 'vitest';

import LandingPage from '../src/pages/LandingPage';

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock('../src/contexts/AuthContext', () => ({
  useAuth: () => ({ session: null, loading: true }),
}));

vi.mock('../src/services/getGenerationStatsApi', () => ({
  GetGenerationStatsApiService: {
    getGenerationStats: vi.fn().mockResolvedValue({
      generation_count: 0,
      brick_count: 0,
    }),
  },
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

describe('LandingPage headline', () => {
  it('shows "Create" in the main heading copy', () => {
    const container = document.createElement('div');
    document.body.appendChild(container);
    const root = createRoot(container);

    try {
      act(() => {
        root.render(<LandingPage />);
      });

      const heading = container.querySelector('h1');
      expect(heading?.textContent).toContain('Imagine. Create. Build.');
    } finally {
      act(() => {
        root.unmount();
      });
      container.remove();
    }
  });
});
