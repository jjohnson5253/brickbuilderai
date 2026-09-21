const DEFAULT_GITHUB_REPO_URL = "https://github.com/jjohnson5253/brickbuilderai";
const configuredGithubRepoUrl = import.meta.env.VITE_GITHUB_REPO_URL?.trim();

export const BRICKBUILDER_GITHUB_REPO_URL = configuredGithubRepoUrl || DEFAULT_GITHUB_REPO_URL;
