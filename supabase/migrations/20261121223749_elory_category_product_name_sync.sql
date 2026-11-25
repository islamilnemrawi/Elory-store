-- Keep products.category (legacy text relation) synchronized when staff renames a category.
-- The trigger is narrowly scoped and verifies product-edit permission before bypassing RLS.
create or replace function public.elory_sync_products_after_category_rename()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
  if new.name is distinct from old.name then
    if auth.uid() is null
       or not public.has_staff_permission('products.edit'::text) then
      raise exception 'Missing products.edit permission to rename a category with assigned products'
        using errcode = '42501';
    end if;

    update public.products
       set category = new.name
     where category is not null
       and lower(btrim(category)) = lower(btrim(old.name));
  end if;
  return new;
end;
$$;

revoke all on function public.elory_sync_products_after_category_rename() from public, anon, authenticated;

drop trigger if exists elory_sync_products_after_category_rename on public.categories;
create trigger elory_sync_products_after_category_rename
after update of name on public.categories
for each row
when (old.name is distinct from new.name)
execute function public.elory_sync_products_after_category_rename();

-- Backfill the already-renamed makeup category. Product IDs, prices, stock,
-- images, active/featured flags, and every unrelated product field stay unchanged.
update public.products p
   set category = c.name
  from public.categories c
 where c.active is true
   and lower(btrim(c.name)) = lower(btrim('مكياج'))
   and lower(btrim(p.category)) = lower(btrim('التجميل'));
