import { describe, expect, it } from 'vitest';
import type { LDrawPart } from '../src/utils/ldrawParser';
import {
  buildInteractiveInstructionsUrl,
  buildHighlightedStepMpd,
  createInstructionSteps,
  rebuildInstructionMpd,
} from '../src/utils/instructionUtils';

const parts = (count: number): LDrawPart[] => Array.from({ length: count }, (_, index) => ({
  colorCode: 4,
  x: index * 20,
  y: 0,
  z: 0,
  matrix: [1, 0, 0, 0, 1, 0, 0, 0, 1],
  filename: '3001.dat',
}));

describe('instruction utilities', () => {
  it.each([
    [5, [5]],
    [10, [10]],
    [11, [6, 5]],
    [20, [10, 10]],
    [21, [7, 7, 7]],
  ])('balances %i pieces into steps containing five to ten pieces', (count, sizes) => {
    const steps = createInstructionSteps(parts(count));

    expect(steps.map((step) => step.parts.length)).toEqual(sizes);
    expect(steps.at(-1)?.cumulativeParts).toHaveLength(count);
  });

  it('keeps a model with fewer than five total pieces in one step', () => {
    expect(createInstructionSteps(parts(4))).toHaveLength(1);
    expect(createInstructionSteps(parts(4))[0].parts).toHaveLength(4);
  });

  it('rebuilds MPD boundaries to match the balanced instruction steps', () => {
    const mpd = [
      '0 FILE model.ldr',
      '0 Name: model.ldr',
      ...parts(11).map((part) =>
        `1 ${part.colorCode} ${part.x} ${part.y} ${part.z} ${part.matrix.join(' ')} ${part.filename}`),
      '0 STEP',
      '0 FILE 3001.dat',
      '0 Brick',
    ].join('\n');

    const rebuilt = rebuildInstructionMpd(mpd, createInstructionSteps(parts(11)));
    const mainModel = rebuilt.split('0 FILE 3001.dat')[0];

    expect(mainModel.match(/^0 STEP$/gm)).toHaveLength(2);
    expect(mainModel.match(/^1 /gm)).toHaveLength(11);
    expect(rebuilt).toContain('0 FILE 3001.dat\n0 Brick');
  });

  it('grays earlier pieces while retaining current-step colors', () => {
    const modelParts = parts(11);
    const mpd = [
      '0 FILE model.ldr',
      ...modelParts.map((part) =>
        `1 ${part.colorCode} ${part.x} ${part.y} ${part.z} ${part.matrix.join(' ')} ${part.filename}`),
    ].join('\n');

    const highlighted = buildHighlightedStepMpd(
      mpd,
      createInstructionSteps(modelParts),
      1,
    );

    expect(highlighted.match(/^1 7 /gm)).toHaveLength(6);
    expect(highlighted.match(/^1 4 /gm)).toHaveLength(5);
  });

  it('builds encoded links to the interactive 3-D step', () => {
    expect(buildInteractiveInstructionsUrl(
      'https://brickbuilder.ai',
      'generation/id',
      3,
    )).toBe('https://brickbuilder.ai/instructions?id=generation%2Fid&step=3');
  });
});
