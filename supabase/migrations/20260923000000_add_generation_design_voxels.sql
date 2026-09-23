-- Voxels an LLM (/llmToBricks) design was built from, in xyzrgb format. Kept separately from
-- xyzrgb_url (which block-editor saves replace) as the source for /resizeModel.
alter table public.generations
add column if not exists design_voxels_url text;
