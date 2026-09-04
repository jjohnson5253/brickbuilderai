import type { LDrawPart, LDrawStep } from './ldrawParser';

const MIN_PARTS_PER_STEP = 5;
const MAX_PARTS_PER_STEP = 10;

export const createInstructionSteps = (parts: LDrawPart[]): LDrawStep[] => {
  if (parts.length === 0) return [];

  const stepCount = Math.ceil(parts.length / MAX_PARTS_PER_STEP);
  const baseSize = Math.floor(parts.length / stepCount);
  const largerSteps = parts.length % stepCount;
  const steps: LDrawStep[] = [];
  let partIndex = 0;

  for (let index = 0; index < stepCount; index++) {
    const stepSize = baseSize + (index < largerSteps ? 1 : 0);
    const stepParts = parts.slice(partIndex, partIndex + stepSize);
    partIndex += stepSize;
    steps.push({
      stepNumber: index + 1,
      parts: stepParts,
      cumulativeParts: parts.slice(0, partIndex),
    });
  }

  return steps;
};

const partToLDrawLine = (part: LDrawPart) =>
  `1 ${part.colorCode} ${part.x} ${part.y} ${part.z} ${part.matrix.join(' ')} ${part.filename}`;

export const rebuildInstructionMpd = (mpdContent: string, steps: LDrawStep[]): string => {
  const lines = mpdContent.split('\n');
  const firstPartIndex = lines.findIndex((line) => line.trim().startsWith('1 '));
  const subfileStartIndex = lines.findIndex(
    (line, index) => index > 0 && line.trim().startsWith('0 FILE'),
  );
  const header = lines.slice(0, firstPartIndex === -1 ? lines.length : firstPartIndex);
  const subfiles = subfileStartIndex === -1 ? [] : lines.slice(subfileStartIndex);
  const instructionLines = steps.flatMap((step) => [
    ...step.parts.map(partToLDrawLine),
    '0 STEP',
  ]);

  return [...header, ...instructionLines, ...subfiles].join('\n');
};

export const buildHighlightedStepMpd = (
  mpdContent: string,
  steps: LDrawStep[],
  stepIndex: number,
): string => {
  const visibleSteps = steps.slice(0, stepIndex + 1).map((step, index) => ({
    ...step,
    parts: index === stepIndex
      ? step.parts
      : step.parts.map((part) => ({ ...part, colorCode: 7 })),
  }));

  return rebuildInstructionMpd(mpdContent, visibleSteps);
};

export const buildInteractiveInstructionsUrl = (
  origin: string,
  generationId?: string | null,
  step?: number,
): string => {
  const url = new URL('/instructions', origin);
  if (generationId) url.searchParams.set('id', generationId);
  if (step) url.searchParams.set('step', String(step));
  return url.toString();
};

export { MIN_PARTS_PER_STEP, MAX_PARTS_PER_STEP };
