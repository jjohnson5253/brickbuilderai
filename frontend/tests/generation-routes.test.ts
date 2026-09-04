import { describe, expect, it } from 'vitest';
import { getGeneratedModelPath } from '../src/utils/generationRoutes';

describe('generation routes', () => {
  it('builds a generated model path for a history entry', () => {
    expect(getGeneratedModelPath('generation-123')).toBe(
      '/generated-model?id=generation-123',
    );
  });

  it('encodes generation IDs before adding them to the query string', () => {
    expect(getGeneratedModelPath('generation?id=123')).toBe(
      '/generated-model?id=generation%3Fid%3D123',
    );
  });
});
