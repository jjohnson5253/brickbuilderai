export const MAX_IMAGES = 4;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export const IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
export const PROTECTED_BRANCHES = new Set(['main', 'staging']);

export function isChangeBranch(branch) {
  return typeof branch === 'string'
    && /^[a-zA-Z0-9._/-]{1,150}$/.test(branch)
    && !PROTECTED_BRANCHES.has(branch);
}

export function validateChange(description, files = []) {
  if (typeof description !== 'string' || !description.trim() || description.length > 8000) {
    throw new Error('Describe the change in 1–8,000 characters.');
  }
  if (!Array.isArray(files) || files.length > MAX_IMAGES) {
    throw new Error(`Attach no more than ${MAX_IMAGES} screenshots.`);
  }
  for (const file of files) {
    if (!IMAGE_TYPES.has(file.type) || !Number.isFinite(file.size)
        || file.size < 1 || file.size > MAX_IMAGE_BYTES) {
      throw new Error('Screenshots must be PNG, JPEG, or WebP files under 5 MB each.');
    }
  }
  return description.trim();
}

export function parseGitHubVercelPreview(event) {
  if (event?.action !== 'vercel_preview') return null;
  const sha = event.sha;
  const rawUrl = event.url;
  if (typeof sha !== 'string' || !/^[0-9a-f]{40}$/i.test(sha)
      || typeof rawUrl !== 'string') return null;
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== 'https:' || url.username || url.password
        || !url.hostname.endsWith('.vercel.app')) return null;
    return { sha: sha.toLowerCase(), url: url.origin };
  } catch {
    return null;
  }
}

export function previewAuthLink(previewUrl, requestId, props = {}) {
  const url = new URL(previewUrl);
  url.searchParams.set('change_request', requestId);
  const hash = typeof props?.hashed_token === 'string' ? props.hashed_token : '';
  const type = typeof props?.verification_type === 'string' ? props.verification_type : 'magiclink';
  if (!hash || !['magiclink', 'email'].includes(type))
    throw new Error('Supabase did not return a usable preview sign-in token.');
  url.searchParams.set('preview_login', '1');
  url.searchParams.set('token_hash', hash);
  url.searchParams.set('type', type);
  return url.toString();
}

export function previewEmailMessage(signedPreviewUrl, pr) {
  const title = typeof pr?.title === 'string' ? pr.title.trim() : '';
  const branch = typeof pr?.head?.ref === 'string' ? pr.head.ref : '';
  const rawPullUrl = typeof pr?.html_url === 'string' ? pr.html_url : '';
  let pullUrl;
  try {
    const parsed = new URL(rawPullUrl);
    if (parsed.protocol !== 'https:' || parsed.hostname !== 'github.com') throw new Error();
    pullUrl = parsed.toString();
  } catch {
    throw new Error('GitHub did not return a usable pull request link.');
  }
  if (!title || !branch) throw new Error('GitHub did not return complete pull request details.');

  return {
    subject: `BrickBuilder preview ready: ${title}`,
    lines: [
      `Preview: ${signedPreviewUrl}`,
      `Pull request: ${title}`,
      `GitHub: ${pullUrl}`,
      `Branch: ${branch}`,
      'The preview link signs you back into the app while its one-time token is valid.',
    ],
  };
}

export function matchesChangePreview(row, branch, deploymentSha, origin) {
  if (!row || !origin) return false;
  if (deploymentSha !== undefined && deploymentSha !== null && deploymentSha !== '') {
    return typeof branch === 'string' && branch === row.branch
      && typeof deploymentSha === 'string' && /^[0-9a-f]{40}$/i.test(deploymentSha)
      && deploymentSha.toLowerCase() === String(row.notified_sha || '').toLowerCase();
  }
  try {
    return new URL(origin).hostname === new URL(row.preview_url).hostname;
  } catch {
    return false;
  }
}

export function taskPullNumber(task) {
  const id = task?.artifacts?.find((a) => a.provider === 'github' && a.type === 'pull')?.data?.id;
  return Number.isInteger(id) && id > 0 ? id : null;
}

export function taskBranchName(task) {
  const branch = task?.artifacts?.find((a) =>
    a.provider === 'github' && a.type === 'branch')?.data?.head_ref;
  return isChangeBranch(branch) ? branch : null;
}

export function pullReadyRequest(pr) {
  if (!pr?.draft) return null;
  if (typeof pr.node_id !== 'string' || !pr.node_id || pr.node_id.length > 200) {
    throw new Error('The draft pull request is missing its GitHub node ID.');
  }
  return {
    query: `mutation MarkPullRequestReady($pullRequestId: ID!) {
      markPullRequestReadyForReview(input: { pullRequestId: $pullRequestId }) {
        pullRequest { id isDraft }
      }
    }`,
    variables: { pullRequestId: pr.node_id },
  };
}

export function parseGitHubAgentCompletion(eventName, event) {
  if (eventName !== 'pull_request'
      || !['review_requested', 'ready_for_review'].includes(event?.action)) return null;
  const pr = event.pull_request;
  if (!Number.isInteger(pr?.number) || !/^[0-9a-f]{40}$/i.test(pr?.head?.sha || '')
      || pr?.base?.ref !== 'staging' || !isChangeBranch(pr?.head?.ref)
      || !String(pr?.user?.login || '').toLowerCase().includes('copilot')
      || pr?.user?.type !== 'Bot') return null;
  return { number: pr.number, sha: pr.head.sha.toLowerCase(), branch: pr.head.ref };
}
