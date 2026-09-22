import { describe, expect, it } from 'vitest';
import {
  isChangeBranch, parseGitHubAgentCompletion, parseGitHubVercelPreview,
  previewAuthLink, previewEmailMessage, taskBranchName, taskPullNumber, validateChange,
} from '../../supabase/functions/_shared/change-request-spec.js';
import { storedScreenshotPaths } from '../../supabase/functions/_shared/change-request-storage.js';
import emailAllowlistMigration from '../../supabase/migrations/20260921000001_add_feedback_email_allowlist.sql?raw';

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

  it('uses GitHub-owned task artifacts and validates Copilot completion', () => {
    expect(taskPullNumber({ artifacts: [{ provider: 'github', type: 'pull', data: { id: 42 } }] })).toBe(42);
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
});
