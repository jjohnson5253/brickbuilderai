import { describe, expect, it, vi } from 'vitest';

import {
  inspectRailwayProject,
  resolveRailwayPreviewBackend,
} from '../scripts/railway-preview.mjs';

function railwayProject({
  environmentName,
  domain,
  serviceName = 'brickai-backend',
}: {
  environmentName?: string;
  domain?: string;
  serviceName?: string;
}) {
  const environmentId = 'environment-id';
  return {
    environments: {
      edges: environmentName
        ? [{ node: { id: environmentId, name: environmentName } }]
        : [],
    },
    services: {
      edges: [
        {
          node: {
            name: serviceName,
            serviceInstances: {
              edges: environmentName
                ? [{
                    node: {
                      environmentId,
                      domains: {
                        serviceDomains: domain ? [{ domain }] : [],
                        customDomains: [],
                      },
                    },
                  }]
                : [],
            },
          },
        },
      ],
    },
  };
}

describe('Railway preview backend resolution', () => {
  it('matches Railway environment names by PR suffix', () => {
    expect(
      inspectRailwayProject(
        railwayProject({
          environmentName: 'brickbuilderai-pr-86',
          domain: 'preview.example.com',
        }),
        '86',
        'brickai-backend',
      ),
    ).toEqual({ status: 'resolved', backendUrl: 'https://preview.example.com' });
  });

  it('waits for the PR environment and domain to become available', async () => {
    const loadProject = vi
      .fn()
      .mockResolvedValueOnce(railwayProject({}))
      .mockResolvedValueOnce(railwayProject({ environmentName: 'pr-86' }))
      .mockResolvedValueOnce(
        railwayProject({ environmentName: 'pr-86', domain: 'preview.example.com' }),
      );
    const sleep = vi.fn().mockResolvedValue(undefined);

    await expect(
      resolveRailwayPreviewBackend({
        loadProject,
        prId: '86',
        serviceName: 'brickai-backend',
        maxAttempts: 3,
        retryDelayMs: 10,
        sleep,
      }),
    ).resolves.toBe('https://preview.example.com');
    expect(loadProject).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(10);
  });

  it('falls back after the bounded retry window expires', async () => {
    const loadProject = vi.fn().mockResolvedValue(railwayProject({}));
    const sleep = vi.fn().mockResolvedValue(undefined);
    const log = vi.fn();

    await expect(
      resolveRailwayPreviewBackend({
        loadProject,
        prId: '86',
        serviceName: 'brickai-backend',
        maxAttempts: 3,
        retryDelayMs: 10,
        sleep,
        log,
      }),
    ).resolves.toBeNull();
    expect(loadProject).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenCalledTimes(2);
    expect(log).toHaveBeenLastCalledWith(
      expect.stringContaining('Railway was not ready after 3 attempts'),
    );
  });

  it('does not retry a missing backend service', async () => {
    const loadProject = vi.fn().mockResolvedValue(
      railwayProject({ serviceName: 'different-service' }),
    );
    const sleep = vi.fn();

    await expect(
      resolveRailwayPreviewBackend({
        loadProject,
        prId: '86',
        serviceName: 'brickai-backend',
        sleep,
      }),
    ).resolves.toBeNull();
    expect(loadProject).toHaveBeenCalledOnce();
    expect(sleep).not.toHaveBeenCalled();
  });
});
