import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const unusedDependencies = [
  '@react-three/drei',
  '@react-three/fiber',
  '@stripe/stripe-js',
  '@types/react-router-dom',
  'cors',
  'dotenv',
  'express',
  'resend',
  'stripe',
];

describe('application dependencies', () => {
  it('does not install unused client and server libraries', () => {
    const packageJson = JSON.parse(
      readFileSync(join(process.cwd(), 'package.json'), 'utf8'),
    );
    const dependencies = {
      ...packageJson.dependencies,
      ...packageJson.devDependencies,
    };

    expect(unusedDependencies.filter((name) => name in dependencies)).toEqual([]);
  });
});
