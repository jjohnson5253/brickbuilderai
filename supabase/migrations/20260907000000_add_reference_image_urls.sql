alter table public.generations
add column if not exists reference_image_urls jsonb;
