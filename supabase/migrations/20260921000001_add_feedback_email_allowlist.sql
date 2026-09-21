-- Pre-authorize feedback users who have not created a Supabase Auth account yet.
-- The Edge Function normalizes authenticated addresses before checking this table.
create table public.change_request_email_access (
  email text primary key check (email = lower(trim(email)) and length(email) between 3 and 320),
  granted_at timestamptz not null default now()
);

alter table public.change_request_email_access enable row level security;
revoke all on public.change_request_email_access from anon, authenticated;
