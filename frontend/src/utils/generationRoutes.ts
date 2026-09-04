export const getGeneratedModelPath = (generationId: string): string =>
  `/generated-model?id=${encodeURIComponent(generationId)}`;
