-- Extend change requests to coordinate exact-commit Expo/TestFlight previews.
-- Build artifacts remain in Expo and Apple; only delivery metadata is stored.
alter table public.change_requests
  add column target text not null default 'web'
    check (target in ('web', 'ios')),
  add column mobile_build_sha text,
  add column mobile_build_url text,
  add column testflight_url text,
  add column mobile_email_sent_at timestamptz;

alter table public.change_requests
  drop constraint if exists change_requests_status_check;

alter table public.change_requests
  add constraint change_requests_status_check check (status in
    ('queued', 'working', 'building', 'preview_ready', 'approved', 'failed'));
