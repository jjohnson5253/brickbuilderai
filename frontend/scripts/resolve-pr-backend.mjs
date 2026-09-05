#!/usr/bin/env node
/**
 * Runs as an npm `prebuild` hook on Vercel.
 *
 * When Vercel builds a *preview* deployment for a pull request, Railway (if PR
 * Environments are enabled) spins up a matching temporary backend for that
 * same PR. This script looks up that backend's public domain via the Railway
 * GraphQL API and writes it into `.env.local` as VITE_RAILWAY_API_URL_STAGING,
 * so the preview frontend talks to the PR's own backend instead of the shared
 * `staging` Railway service.
 *
 * It is intentionally best-effort: any failure (missing config, PR
 * environment not up yet, API error, unexpected schema) is logged and the
 * script exits 0 without writing anything, so the build falls back to
 * whatever VITE_RAILWAY_API_URL_STAGING is already configured in Vercel.
 *
 * Required Vercel project env vars for this to activate:
 *   RAILWAY_API_TOKEN            - Railway account or workspace token
 *   RAILWAY_PROJECT_ID           - the Railway project containing the backend
 *   RAILWAY_BACKEND_SERVICE_NAME - name of the backend service in Railway
 *                                  (defaults to "backend")
 */
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const RAILWAY_API_URL = 'https://backboard.railway.com/graphql/v2';

function log(message) {
  console.log(`[resolve-pr-backend] ${message}`);
}

async function main() {
  const prId = process.env.VERCEL_GIT_PULL_REQUEST_ID;
  const vercelEnv = process.env.VERCEL_ENV;

  if (vercelEnv !== 'preview' || !prId) {
    log('Not a PR preview build; skipping Railway PR backend lookup.');
    return;
  }

  const token = process.env.RAILWAY_API_TOKEN;
  const projectId = process.env.RAILWAY_PROJECT_ID;
  const serviceName = process.env.RAILWAY_BACKEND_SERVICE_NAME || 'backend';

  if (!token || !projectId) {
    log(
      'RAILWAY_API_TOKEN and/or RAILWAY_PROJECT_ID are not set; skipping. ' +
        'Set them as Vercel project env vars to enable per-PR backend resolution.'
    );
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
      return;
    }
  } catch (err) {
    log(`Railway API request threw: ${err}`);
    return;
  }

  const project = json?.data?.project;
  if (!project) {
    log('Railway API response missing project data; skipping.');
    return;
  }

  // Railway names PR environments like "pr-<number>".
  const envEdges = project.environments?.edges ?? [];
  const prEnv = envEdges.find(
    (e) => e.node?.name?.toLowerCase() === `pr-${prId}`.toLowerCase()
  );
  if (!prEnv) {
    log(
      `No Railway environment named "pr-${prId}" found yet (it may still be ` +
        `spinning up). Falling back to the default configured backend.`
    );
    return;
  }
  const environmentId = prEnv.node.id;

  const serviceEdges = project.services?.edges ?? [];
  const backendService = serviceEdges.find((e) => e.node?.name === serviceName);
  if (!backendService) {
    log(`No Railway service named "${serviceName}" found in this project; skipping.`);
    return;
  }

  const instanceEdges = backendService.node.serviceInstances?.edges ?? [];
  const instance = instanceEdges.find((e) => e.node?.environmentId === environmentId);
  const domain =
    instance?.node?.domains?.serviceDomains?.[0]?.domain ??
    instance?.node?.domains?.customDomains?.[0]?.domain;

  if (!domain) {
    log(`No domain found for service "${serviceName}" in environment "pr-${prId}"; skipping.`);
    return;
  }

  const backendUrl = `https://${domain}`;
  const envFilePath = path.resolve(
    path.dirname(fileURLToPath(import.meta.url)),
    '..',
    '.env.local'
  );
  writeFileSync(
    envFilePath,
    `VITE_API_MODE=railway_staging\nVITE_RAILWAY_API_URL_STAGING=${backendUrl}\n`
  );
  log(`Resolved PR backend to ${backendUrl}; wrote ${envFilePath}.`);
}

main().catch((err) => {
  log(`Unexpected error, skipping: ${err}`);
});
