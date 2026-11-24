begin;

insert into storage.buckets (
  id,
  name,
  public,
  file_size_limit,
  allowed_mime_types
)
values (
  'hero-ads',
  'hero-ads',
  true,
  52428800,
  array[
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/avif',
    'video/mp4',
    'video/webm'
  ]::text[]
)
on conflict (id) do update
set
  name = excluded.name,
  public = excluded.public,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "Elory hero ads staff upload" on storage.objects;
create policy "Elory hero ads staff upload"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'hero-ads'
  and public.elory_can_edit_site()
);

drop policy if exists "Elory hero ads staff delete" on storage.objects;
create policy "Elory hero ads staff delete"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'hero-ads'
  and public.elory_can_edit_site()
);

commit;
