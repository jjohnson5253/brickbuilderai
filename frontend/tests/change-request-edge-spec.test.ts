import { describe, expect, it } from 'vitest';
import {
  isChangeBranch, matchesChangePreview, parseGitHubAgentCompletion,
  parseGitHubVercelPreview, parseTestFlightReady, previewAuthLink,
  previewEmailMessage, taskBranchName, taskPullNumber, testFlightEmailMessage,
  validateChange,
} from '../../supabase/functions/_shared/change-request-spec.js';
import { storedScreenshotPaths } from '../../supabase/functions/_shared/change-request-storage.js';
import emailAllowlistMigration from '../../supabase/migrations/20260921000001_add_feedback_email_allowlist.sql?raw';
import mobileMigration from '../../supabase/migrations/20260923000001_add_mobile_change_request_builds.sql?raw';
import deliveryWorkflow from '../../.github/workflows/change-request-vercel-preview.yml?raw';

describe('change request Edge contract', () => {
  it('validates product text, image limits, and work branches', () => {
    expect(validateChange(' Improve the editor ', [{ type: 'image/png', size: 20 }]))
      .toBe('Improve the editor');
    expect(() => validateChange('')).toThrow();
    expect(() => validateChange('x', [{ type: 'text/plain', size: 20 }])).toThrow();
    expect(isChangeBranch('copilot/editor-change')).toBe(true);
    expect(isChangeBranch('staging')).toBe(false);
  });

  it('accepts only exact Vercel preview events', () => {
    const event = { action: 'vercel_preview', sha: 'A'.repeat(40), url: 'https://branch.vercel.app/path' };
    expect(parseGitHubVercelPreview(event)).toEqual({ sha: 'a'.repeat(40), url: 'https://branch.vercel.app' });
    expect(parseGitHubVercelPreview({ ...event, url: 'https://vercel.app.evil.test' })).toBeNull();
  });

  it('accepts only exact Expo TestFlight-ready events', () => {
    const event = {
      action: 'testflight_ready',
      pr_number: 42,
      sha: 'A'.repeat(40),
      build_url: 'https://expo.dev/accounts/brickbuilder/projects/app/builds/build-1',
    };
    expect(parseTestFlightReady(event)).toEqual({
      prNumber: 42,
      sha: 'a'.repeat(40),
      buildUrl: event.build_url,
    });
    expect(parseTestFlightReady({
      ...event,
      build_url: 'https://expo.dev.evil.test/builds/build-1',
    })).toBeNull();
  });

  it('requires and embeds a Supabase magic-link token', () => {
    expect(previewAuthLink('https://branch.vercel.app', 'req-1', {
      hashed_token: 'hash', verification_type: 'magiclink',
    })).toContain('preview_login=1');
    expect(() => previewAuthLink('https://branch.vercel.app', 'req-1')).toThrow('usable');
  });

  it('includes the pull request title and GitHub link in preview emails', () => {
    const message = previewEmailMessage('https://branch.vercel.app?token_hash=hash', {
      title: 'Improve the model editor',
      html_url: 'https://github.com/example/app/pull/42',
      head: { ref: 'copilot/improve-editor' },
    });
    expect(message.subject).toContain('Improve the model editor');
    expect(message.lines).toContain('Pull request: Improve the model editor');
    expect(message.lines).toContain('GitHub: https://github.com/example/app/pull/42');
    expect(() => previewEmailMessage('https://branch.vercel.app', {
      title: 'Unsafe link', html_url: 'https://example.com/pull/42', head: { ref: 'copilot/change' },
    })).toThrow('usable pull request link');
  });

  it('builds a validated TestFlight delivery email', () => {
    const message = testFlightEmailMessage(
      'https://testflight.apple.com/join/BrickBuilder',
      'https://expo.dev/accounts/brickbuilder/projects/app/builds/build-1',
      {
        title: 'Adjust the iPhone editor',
        html_url: 'https://github.com/example/app/pull/42',
        head: { ref: 'copilot/iphone-editor' },
      },
    );
    expect(message.subject).toContain('Adjust the iPhone editor');
    expect(message.lines[0]).toContain('testflight.apple.com/join/BrickBuilder');
    expect(() => testFlightEmailMessage(
      'https://testflight.apple.com.evil.test/join/fake',
      'https://expo.dev/builds/build-1',
      { title: 'Unsafe', html_url: 'https://github.com/example/app/pull/42', head: { ref: 'copilot/change' } },
    )).toThrow('not usable');
  });

  it('allows exact-SHA approval from a native build without a browser origin', () => {
    const sha = 'a'.repeat(40);
    expect(matchesChangePreview({
      branch: 'copilot/iphone-editor', notified_sha: sha,
    }, 'copilot/iphone-editor', sha, '')).toBe(true);
  });

  it('uses GitHub-owned task artifacts and validates Copilot completion', () => {
    expect(taskPullNumber({ artifacts: [{ provider: 'github', type: 'pull', data: { id: 42 } }] })).toBe(42);
    expect(taskPullNumber({ artifacts: [{
      provider: 'github', type: 'github_resource', data: { type: 'pull', id: 9001, state: 'draft' },
    }] })).toBe(9001);
    expect(taskPullNumber({ artifacts: [{
      provider: 'github', type: 'github_resource', data: { type: 'issue', id: 9001 },
    }] })).toBeNull();
    expect(taskBranchName({ artifacts: [{
      provider: 'github', type: 'branch', data: { base_ref: 'staging', head_ref: 'copilot/change' },
    }] })).toBe('copilot/change');
    expect(taskBranchName({ artifacts: [{
      provider: 'github', type: 'branch', data: { base_ref: 'staging', head_ref: 'main' },
    }] })).toBeNull();
    const event = { action: 'review_requested', pull_request: {
      number: 42, base: { ref: 'staging' }, head: { ref: 'copilot/change', sha: 'a'.repeat(40) },
      user: { login: 'Copilot', type: 'Bot' },
    } };
    expect(parseGitHubAgentCompletion('pull_request', event)).toMatchObject({ number: 42 });
  });

  it('only purges screenshot paths owned by that request', () => {
    expect(storedScreenshotPaths({ id: 'req', screenshots: ['req/a.png', 'other/b.png', 'req/../x'] }))
      .toEqual(['req/a.png']);
  });

  it('keeps the normalized email allowlist private', () => {
    expect(emailAllowlistMigration).toContain(
      'alter table public.change_request_email_access enable row level security',
    );
    expect(emailAllowlistMigration).toContain(
      'revoke all on public.change_request_email_access from anon, authenticated',
    );
    expect(emailAllowlistMigration).toContain('email = lower(trim(email))');
  });

  it('adds iOS build state and an exact-commit EAS delivery workflow', () => {
    expect(mobileMigration).toContain("check (target in ('web', 'ios'))");
    expect(mobileMigration).toContain("'building'");
    expect(deliveryWorkflow).toContain('EXPO_PUBLIC_CHANGE_REQUEST_ID');
    expect(deliveryWorkflow).toContain('EXPO_PUBLIC_WEB_APP_URL');
    expect(deliveryWorkflow).toContain('eas build --platform ios --profile feedback');
    expect(deliveryWorkflow).toContain("'{action: \"testflight_ready\"");
  });
});
