import type { CommunityGeneration } from '../services/getCommunityGenerationsApi';

// A model shown in the landing page featured carousel. Items can come from the
// static demo metadata or from highlighted community generations.
export type FeaturedModel = {
  id: string;
  title: string;
  imgUrl: string;
  pieces?: number;
  cost?: number;
  source: 'demo' | 'community';
};

const MAX_TITLE_LENGTH = 60;

function truncateTitle(title: string): string {
  return title.length > MAX_TITLE_LENGTH
    ? `${title.slice(0, MAX_TITLE_LENGTH - 3)}...`
    : title;
}

/**
 * Convert a highlighted community generation into a featured carousel model.
 * Returns null for generations that are not completed or have no image to show.
 */
export function communityGenerationToFeaturedModel(
  generation: CommunityGeneration
): FeaturedModel | null {
  if (generation.status !== 'completed') return null;
  const imgUrl =
    generation.preview_image_url ||
    generation.external_image_url ||
    generation.processed_image_url ||
    null;
  if (!imgUrl) return null;

  const title =
    generation.name?.trim() || generation.prompt?.trim() || 'Community Model';

  return {
    id: generation.id,
    title: truncateTitle(title),
    imgUrl,
    pieces: generation.brick_count ?? undefined,
    source: 'community',
  };
}

/**
 * Merge highlighted community models with the static demo models, keeping the
 * community models first and dropping demo duplicates so the marquee always
 * has enough cards to fill the strip.
 */
export function mergeFeaturedModels(
  communityModels: FeaturedModel[],
  demoModels: FeaturedModel[]
): FeaturedModel[] {
  const seen = new Set(communityModels.map((model) => model.id));
  return [
    ...communityModels,
    ...demoModels.filter((model) => !seen.has(model.id)),
  ];
}
