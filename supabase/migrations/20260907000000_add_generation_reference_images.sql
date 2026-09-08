alter table public.generations
add column if not exists reference_images jsonb not null default '{}'::jsonb;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'generations_reference_images_object'
      and conrelid = 'public.generations'::regclass
  ) then
    alter table public.generations
    add constraint generations_reference_images_object
    check (jsonb_typeof(reference_images) = 'object');
  end if;
end
$$;
