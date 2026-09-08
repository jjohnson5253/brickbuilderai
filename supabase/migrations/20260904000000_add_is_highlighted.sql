alter table public.generations
add column if not exists is_highlighted boolean not null default false;

create index if not exists generations_is_highlighted_idx
on public.generations (is_highlighted)
where is_highlighted;
