import { describe, expect, it } from 'vitest';
import type { CommunityGeneration } from '../src/services/getCommunityGenerationsApi';
import {
  communityGenerationToFeaturedModel,
  mergeFeaturedModels,
  type FeaturedModel,
} from '../src/utils/featuredModels';

const generation = (overrides: Partial<CommunityGeneration> = {}): CommunityGeneration => ({
  id: 'gen-1',
  user_id: 'user-1',
  user_type: 'authenticated',
  prompt: 'a castle',
  name: 'Castle',
  detail_level: 40,
  endpoint: '/textToBricks',
  created_at: '2026-01-01T00:00:00Z',
  status: 'completed',
  preview_image_url: 'https://example.com/preview.png',
  is_community: true,
  is_highlighted: true,
  brick_count: 231,
  ...overrides,
});

describe('communityGenerationToFeaturedModel', () => {
  it('maps a completed highlighted generation to a featured model', () => {
    expect(communityGenerationToFeaturedModel(generation())).toEqual({
      id: 'gen-1',
      title: 'Castle',
      imgUrl: 'https://example.com/preview.png',
      pieces: 231,
      source: 'community',
    });
  });

  it('falls back to prompt and secondary images, omitting missing pieces', () => {
    const model = communityGenerationToFeaturedModel(generation({
      name: '  ',
      preview_image_url: null,
      external_image_url: 'https://example.com/external.png',
      brick_count: null,
    }));
    expect(model).toMatchObject({ title: 'a castle', imgUrl: 'https://example.com/external.png' });
    expect(model?.pieces).toBeUndefined();
  });

  it('truncates long titles', () => {
    const model = communityGenerationToFeaturedModel(generation({ name: 'x'.repeat(80) }));
    expect(model?.title).toHaveLength(60);
    expect(model?.title.endsWith('...')).toBe(true);
  });

  it('rejects generations without an image or not completed', () => {
    expect(communityGenerationToFeaturedModel(generation({ status: 'processing' }))).toBeNull();
    expect(communityGenerationToFeaturedModel(generation({
      preview_image_url: null,
      external_image_url: null,
      processed_image_url: null,
    }))).toBeNull();
  });
});

describe('mergeFeaturedModels', () => {
  const community: FeaturedModel[] = [
    { id: 'gen-1', title: 'Castle', imgUrl: 'a.png', source: 'community' },
  ];
  const demos: FeaturedModel[] = [
    { id: 'gen-1', title: 'Castle Demo', imgUrl: 'b.png', pieces: 10, cost: 5, source: 'demo' },
    { id: 'demo-2', title: 'Link', imgUrl: 'c.png', pieces: 20, cost: 9, source: 'demo' },
  ];

  it('puts community models first and dedupes demo models by id', () => {
    expect(mergeFeaturedModels(community, demos).map((m) => m.id)).toEqual(['gen-1', 'demo-2']);
  });

  it('returns demo models unchanged when there are no community models', () => {
    expect(mergeFeaturedModels([], demos)).toEqual(demos);
  });
});
