alter table public.generations
add column if not exists brick_count bigint
check (brick_count >= 0);

create or replace function public.get_generation_stats()
returns table (
  generation_count bigint,
  brick_count bigint
)
language sql
stable
security definer
set search_path = public
as $$
  select
    count(*)::bigint as generation_count,
    coalesce(sum(g.brick_count), 0)::bigint as brick_count
  from public.generations as g;
$$;

revoke all on function public.get_generation_stats() from public;
revoke all on function public.get_generation_stats() from anon;
revoke all on function public.get_generation_stats() from authenticated;
grant execute on function public.get_generation_stats() to service_role;
