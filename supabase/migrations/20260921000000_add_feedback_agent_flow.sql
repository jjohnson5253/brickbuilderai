-- Service-owned state for the in-app Copilot change-request flow.
create table public.change_request_access (
  user_id uuid primary key references auth.users(id) on delete cascade,
  granted_at timestamptz not null default now()
);

create table public.change_requests (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  email text not null,
  status text not null default 'queued' check (status in
    ('queued', 'working', 'preview_ready', 'approved', 'failed')),
  task_id text,
  branch text,
  pr_number integer,
  preview_url text,
  screenshots jsonb not null default '[]'::jsonb,
  revision integer not null default 1,
  notified_sha text,
  agent_completed_sha text,
  main_pr_url text,
  preview_email_sent_at timestamptz,
  approval_email_sent_at timestamptz,
  failure_email_sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deadline_at timestamptz not null default (now() + interval '3 hours')
);

create index change_requests_pending_idx on public.change_requests (status, deadline_at)
  where status in ('queued', 'working');
create index change_requests_owner_idx on public.change_requests (user_id, created_at desc);
create unique index change_requests_branch_idx on public.change_requests (branch)
  where branch is not null and status <> 'failed';

alter table public.change_request_access enable row level security;
alter table public.change_requests enable row level security;
revoke all on public.change_request_access from anon, authenticated;
revoke all on public.change_requests from anon, authenticated;

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('change-request-images', 'change-request-images', false, 5242880,
  array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do nothing;
