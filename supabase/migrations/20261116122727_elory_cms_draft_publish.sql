-- Unpublished CMS content is stored separately from the public site config.
-- RLS keeps the draft limited to staff who already have website-edit permission.
create schema if not exists elory_cms_private;
revoke all on schema elory_cms_private from public, anon, authenticated;
grant usage on schema elory_cms_private to authenticated;

create table if not exists elory_cms_private.site_customization_drafts (
  id integer primary key check (id = 1),
  draft_config jsonb not null check (jsonb_typeof(draft_config) = 'object'),
  updated_at timestamptz not null default now()
);

alter table elory_cms_private.site_customization_drafts enable row level security;
revoke all on table elory_cms_private.site_customization_drafts from public, anon, authenticated;
grant select, insert, update, delete on table elory_cms_private.site_customization_drafts to authenticated;

drop policy if exists "authorized staff manage CMS draft" on elory_cms_private.site_customization_drafts;
create policy "authorized staff manage CMS draft"
on elory_cms_private.site_customization_drafts
for all
to authenticated
using (public.elory_can_edit_site())
with check (public.elory_can_edit_site());

create or replace function public.admin_save_site_customization_draft(p_config jsonb)
returns boolean
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if auth.uid() is null or not public.elory_can_edit_site() then
    raise exception 'not_authorized' using errcode = '42501';
  end if;
  if p_config is null or jsonb_typeof(p_config) <> 'object' then
    raise exception 'invalid_site_config' using errcode = '22023';
  end if;

  insert into elory_cms_private.site_customization_drafts (id, draft_config, updated_at)
  values (1, p_config, now())
  on conflict (id) do update
    set draft_config = excluded.draft_config,
        updated_at = excluded.updated_at;

  return true;
end;
$function$;

create or replace function public.admin_get_site_customization_draft()
returns jsonb
language plpgsql
security invoker
set search_path = ''
as $function$
declare
  v_draft jsonb;
begin
  if auth.uid() is null or not public.elory_can_edit_site() then
    raise exception 'not_authorized' using errcode = '42501';
  end if;

  select draft_config
    into v_draft
    from elory_cms_private.site_customization_drafts
   where id = 1;

  return v_draft;
end;
$function$;

create or replace function public.admin_clear_site_customization_draft()
returns boolean
language plpgsql
security invoker
set search_path = ''
as $function$
begin
  if auth.uid() is null or not public.elory_can_edit_site() then
    raise exception 'not_authorized' using errcode = '42501';
  end if;

  delete from elory_cms_private.site_customization_drafts where id = 1;
  return true;
end;
$function$;

revoke all on function public.admin_save_site_customization_draft(jsonb) from public, anon;
revoke all on function public.admin_get_site_customization_draft() from public, anon;
revoke all on function public.admin_clear_site_customization_draft() from public, anon;

grant execute on function public.admin_save_site_customization_draft(jsonb) to authenticated;
grant execute on function public.admin_get_site_customization_draft() to authenticated;
grant execute on function public.admin_clear_site_customization_draft() to authenticated;
