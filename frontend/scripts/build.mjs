#!/usr/bin/env node
/**
 * Replaces `vite build` as the Vercel build command.
 *
 * When Vercel builds a *preview* deployment for a pull request, Railway (if PR
 * Environments are enabled) spins up a matching temporary backend for that
 * same PR. This script looks up that backend's public domain via the Railway
 * GraphQL API and runs `vite build` with VITE_API_MODE/VITE_RAILWAY_API_URL_STAGING
 * overridden directly in that build process's environment, so the preview
 * frontend talks to the PR's own backend instead of the shared `staging`
 * Railway service.
 *
 * A `.env.local` file (or any other env file) can't be used for this: Vite
 * gives already-set process.env values priority over .env* file contents, and
 * Vercel already has VITE_RAILWAY_API_URL_STAGING configured as a project env
 * var for the persistent `staging` backend, so a file-based override would
 * always lose. Spawning `vite build` with an explicit env object is the only
 * way to actually win that precedence.
 *
 * It is intentionally best-effort: any failure (missing config, PR
 * environment not up yet, API error, unexpected schema) is logged and the
 * build proceeds with the default configured backend.
 *
 * Required Vercel project env vars for this to activate:
 *   RAILWAY_API_TOKEN            - Railway account or workspace token
 *   RAILWAY_PROJECT_ID           - the Railway project containing the backend
 *   RAILWAY_BACKEND_SERVICE_NAME - name of the backend service in Railway
 *                                  (defaults to "brickai-backend"; only needed
 *                                  if you rename the Railway service)
 */
import { spawnSync } from 'node:child_process';

const RAILWAY_API_URL = 'https://backboard.railway.com/graphql/v2';

function log(message) {
  console.log(`[build] ${message}`);
}

function runViteBuild(env) {
  const result = spawnSync('npx', ['vite', 'build'], { stdio: 'inherit', env });
  process.exit(result.status ?? 1);
}

async function main() {
  const prId = process.env.VERCEL_GIT_PULL_REQUEST_ID;
  const vercelEnv = process.env.VERCEL_ENV;

  if (vercelEnv !== 'preview' || !prId) {
    log('Not a PR preview build; skipping Railway PR backend lookup.');
    runViteBuild(process.env);
    return;
  }

  const token = process.env.RAILWAY_API_TOKEN;
  const projectId = process.env.RAILWAY_PROJECT_ID;
  const serviceName = process.env.RAILWAY_BACKEND_SERVICE_NAME || 'brickai-backend';

  if (!token || !projectId) {
    log(
      'RAILWAY_API_TOKEN and/or RAILWAY_PROJECT_ID are not set; skipping. ' +
        'Set them as Vercel project env vars to enable per-PR backend resolution.'
    );
    runViteBuild(process.env);
    return;
  }

  const query = `
    query ProjectEnvironmentsAndServices($projectId: String!) {
      project(id: $projectId) {
        environments {
          edges { node { id name } }
        }
        services {
          edges {
            node {
              id
              name
              serviceInstances {
                edges {
                  node {
                    environmentId
                    domains {
                      serviceDomains { domain }
                      customDomains { domain }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  `;

  let json;
  try {
    const response = await fetch(RAILWAY_API_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query, variables: { projectId } }),
    });
    json = await response.json();
    if (!response.ok || json.errors) {
      log(`Railway API request failed: ${response.status} ${JSON.stringify(json.errors)}`);
      runViteBuild(process.env);
      return;
    }
  } catch (err) {
    log(`Railway API request threw: ${err}`);
    runViteBuild(process.env);
    return;
  }

  const project = json?.data?.project;
  if (!project) {
    log('Railway API response missing project data; skipping.');
    runViteBuild(process.env);
    return;
  }

  // Railway names PR environments like "pr-<number>" or "<project-name>-pr-<number>"
  // (observed in practice), so match on a "pr-<number>" suffix rather than an
  // exact string.
  const prSuffix = `pr-${prId}`.toLowerCase();
  const envEdges = project.environments?.edges ?? [];
  const prEnv = envEdges.find((e) => {
    const name = e.node?.name?.toLowerCase() ?? '';
    return name === prSuffix || name.endsWith(`-${prSuffix}`);
  });
  if (!prEnv) {
    log(
      `No Railway environment matching "*${prSuffix}" found yet (it may still be ` +
        `spinning up). Falling back to the default configured backend.`
    );
    runViteBuild(process.env);
    return;
  }
  const environmentId = prEnv.node.id;

  const serviceEdges = project.services?.edges ?? [];
  const backendService = serviceEdges.find((e) => e.node?.name === serviceName);
  if (!backendService) {
    log(`No Railway service named "${serviceName}" found in this project; skipping.`);
    runViteBuild(process.env);
    return;
  }

  const instanceEdges = backendService.node.serviceInstances?.edges ?? [];
  const instance = instanceEdges.find((e) => e.node?.environmentId === environmentId);
  const domain =
    instance?.node?.domains?.serviceDomains?.[0]?.domain ??
    instance?.node?.domains?.customDomains?.[0]?.domain;

  if (!domain) {
    log(`No domain found for service "${serviceName}" in environment "pr-${prId}"; skipping.`);
    runViteBuild(process.env);
    return;
  }

  const backendUrl = `https://${domain}`;
  log(`Resolved PR backend to ${backendUrl}; building with it.`);
  runViteBuild({
    ...process.env,
    VITE_API_MODE: 'railway_staging',
    VITE_RAILWAY_API_URL_STAGING: backendUrl,
  });
}

main().catch((err) => {
  log(`Unexpected error, falling back to default build: ${err}`);
  runViteBuild(process.env);
});
