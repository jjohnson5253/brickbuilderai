const DEFAULT_GITHUB_REPO_URL = "https://github.com/jjohnson5253/brickbuilderai";
const EXPECTED_GITHUB_HOST = "github.com";
const EXPECTED_REPOSITORY_PATH = "/jjohnson5253/brickbuilderai";

function isAllowedGithubRepoUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    const isHttpProtocol = parsed.protocol === "http:" || parsed.protocol === "https:";
    const normalizedHostname = parsed.hostname.toLowerCase();
    const isExpectedHost = normalizedHostname === EXPECTED_GITHUB_HOST;
    const path = parsed.pathname.replace(/\/+$/, "");
    const isExpectedRepository = path === EXPECTED_REPOSITORY_PATH;
    return isHttpProtocol && isExpectedHost && isExpectedRepository;
  } catch {
    return false;
  }
}

export function resolveBrickbuilderGithubRepoUrl(
  configuredUrl: string | undefined | null,
): string {
  const trimmedConfiguredUrl = configuredUrl?.trim();
  return trimmedConfiguredUrl && isAllowedGithubRepoUrl(trimmedConfiguredUrl)
    ? trimmedConfiguredUrl
    : DEFAULT_GITHUB_REPO_URL;
}

const configuredGithubRepoUrl = import.meta.env.VITE_GITHUB_REPO_URL;

export const BRICKBUILDER_GITHUB_REPO_URL =
  resolveBrickbuilderGithubRepoUrl(configuredGithubRepoUrl);
