const DEFAULT_GITHUB_REPO_URL = "https://github.com/jjohnson5253/brickbuilderai";
const configuredGithubRepoUrl = import.meta.env.VITE_GITHUB_REPO_URL?.trim();

function isSafeHttpUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export const BRICKBUILDER_GITHUB_REPO_URL = configuredGithubRepoUrl && isSafeHttpUrl(configuredGithubRepoUrl)
  ? configuredGithubRepoUrl
  : DEFAULT_GITHUB_REPO_URL;
