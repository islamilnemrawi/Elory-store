begin;

create or replace function public.elory_can_edit_site()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select
    public.has_staff_permission('MANAGE_WEBSITE_EDITOR')
    or public.has_staff_permission('site.edit')
    or public.has_staff_permission('website.manage');
$$;

create or replace function public.elory_can_manage_site_images()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select
    public.has_staff_permission('MANAGE_PRODUCTS')
    or public.has_staff_permission('MANAGE_CATEGORIES')
    or public.has_staff_permission('MANAGE_WEBSITE_EDITOR')
    or public.has_staff_permission('products.manage')
    or public.has_staff_permission('categories.manage')
    or public.has_staff_permission('website.manage')
    or public.has_staff_permission('site.edit');
$$;

revoke all on function public.elory_can_edit_site() from public, anon;
revoke all on function public.elory_can_manage_site_images() from public, anon;
grant execute on function public.elory_can_edit_site() to authenticated;
grant execute on function public.elory_can_manage_site_images() to authenticated;

alter policy "Authenticated can manage site customizations"
  on public.site_customizations
  using (public.elory_can_edit_site())
  with check (public.elory_can_edit_site());

drop policy if exists "Staff site customizations insert" on public.site_customizations;
drop policy if exists "Staff site customizations select" on public.site_customizations;
drop policy if exists "Staff site customizations update" on public.site_customizations;
drop policy if exists "Staff site delete permission" on public.site_customizations;
drop policy if exists "Staff site edit permission" on public.site_customizations;
drop policy if exists "Staff site update permission" on public.site_customizations;

update storage.buckets
set
  file_size_limit = 10485760,
  allowed_mime_types = array['image/webp', 'image/jpeg', 'image/png', 'image/avif']
where id = 'product-images';

drop policy if exists "Elory public read product images" on storage.objects;
drop policy if exists "Elory staff upload product images" on storage.objects;
drop policy if exists "Elory staff update product images" on storage.objects;
drop policy if exists "Elory staff delete product images" on storage.objects;

create policy "Elory public read product images"
on storage.objects
for select
to anon, authenticated
using (bucket_id = 'product-images');

create policy "Elory staff upload product images"
on storage.objects
for insert
to authenticated
with check (
  bucket_id = 'product-images'
  and public.elory_can_manage_site_images()
);

create policy "Elory staff update product images"
on storage.objects
for update
to authenticated
using (
  bucket_id = 'product-images'
  and public.elory_can_manage_site_images()
)
with check (
  bucket_id = 'product-images'
  and public.elory_can_manage_site_images()
);

create policy "Elory staff delete product images"
on storage.objects
for delete
to authenticated
using (
  bucket_id = 'product-images'
  and public.elory_can_manage_site_images()
);

commit;