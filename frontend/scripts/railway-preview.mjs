export const DEFAULT_MAX_ATTEMPTS = 30;
export const DEFAULT_RETRY_DELAY_MS = 5_000;

export function inspectRailwayProject(project, prId, serviceName) {
  const serviceEdges = project.services?.edges ?? [];
  const backendService = serviceEdges.find((edge) => edge.node?.name === serviceName);
  if (!backendService) {
    return {
      status: 'failed',
      message: `No Railway service named "${serviceName}" found in this project.`,
    };
  }

  const prSuffix = `pr-${prId}`.toLowerCase();
  const environmentEdges = project.environments?.edges ?? [];
  const prEnvironment = environmentEdges.find((edge) => {
    const name = edge.node?.name?.toLowerCase() ?? '';
    return name === prSuffix || name.endsWith(`-${prSuffix}`);
  });
  if (!prEnvironment) {
    return {
      status: 'pending',
      message: `No Railway environment matching "*${prSuffix}" found yet`,
    };
  }

  const instanceEdges = backendService.node.serviceInstances?.edges ?? [];
  const instance = instanceEdges.find(
    (edge) => edge.node?.environmentId === prEnvironment.node.id,
  );
  const domain =
    instance?.node?.domains?.serviceDomains?.[0]?.domain ??
    instance?.node?.domains?.customDomains?.[0]?.domain;

  if (!domain) {
    return {
      status: 'pending',
      message: `No domain found for service "${serviceName}" in environment "${prEnvironment.node.name}" yet`,
    };
  }

  return { status: 'resolved', backendUrl: `https://${domain}` };
}

export async function resolveRailwayPreviewBackend({
  loadProject,
  prId,
  serviceName,
  maxAttempts = DEFAULT_MAX_ATTEMPTS,
  retryDelayMs = DEFAULT_RETRY_DELAY_MS,
  sleep = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  log = () => {},
}) {
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    const project = await loadProject();
    const result = inspectRailwayProject(project, prId, serviceName);

    if (result.status === 'resolved') {
      return result.backendUrl;
    }
    if (result.status === 'failed') {
      log(`${result.message} Falling back to the default configured backend.`);
      return null;
    }
    if (attempt === maxAttempts) {
      log(
        `${result.message}. Railway was not ready after ${maxAttempts} attempts; ` +
          'falling back to the default configured backend.',
      );
      return null;
    }

    log(
      `${result.message}; waiting ${retryDelayMs}ms before retry ` +
        `${attempt + 1}/${maxAttempts}.`,
    );
    await sleep(retryDelayMs);
  }

  return null;
}
