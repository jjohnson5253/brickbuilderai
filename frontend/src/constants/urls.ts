const DEFAULT_GITHUB_REPO_URL = "https://github.com/jjohnson5253/brickbuilderai";
const EXPECTED_GITHUB_HOST = "github.com";
const EXPECTED_REPOSITORY_PATH = "/jjohnson5253/brickbuilderai";

function getCanonicalGithubRepoUrl(url: URL): string {
  return `${url.protocol}//${url.hostname.toLowerCase()}${EXPECTED_REPOSITORY_PATH}`;
}

function parseAllowedGithubRepoUrl(url: string): URL | null {
  try {
    const parsed = new URL(url);
    const isHttpProtocol = parsed.protocol === "http:" || parsed.protocol === "https:";
    const normalizedHostname = parsed.hostname.toLowerCase();
    const isExpectedHost = normalizedHostname === EXPECTED_GITHUB_HOST;
    const path = parsed.pathname.replace(/\/+$/, "");
    const isExpectedRepository = path === EXPECTED_REPOSITORY_PATH;
    return isHttpProtocol && isExpectedHost && isExpectedRepository ? parsed : null;
  } catch {
    return null;
  }
}

export function resolveBrickbuilderGithubRepoUrl(
  configuredUrl: string | undefined | null,
): string {
  const trimmedConfiguredUrl = configuredUrl?.trim();
  const parsedConfiguredUrl = trimmedConfiguredUrl
    ? parseAllowedGithubRepoUrl(trimmedConfiguredUrl)
    : null;

  return parsedConfiguredUrl
    ? getCanonicalGithubRepoUrl(parsedConfiguredUrl)
    : DEFAULT_GITHUB_REPO_URL;
}

const configuredGithubRepoUrl = import.meta.env.VITE_GITHUB_REPO_URL;

export const BRICKBUILDER_GITHUB_REPO_URL =
  resolveBrickbuilderGithubRepoUrl(configuredGithubRepoUrl);
