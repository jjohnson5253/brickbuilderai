alter table public.generations
add column if not exists segment_mapping jsonb,
add column if not exists segment_ldr_url text;
