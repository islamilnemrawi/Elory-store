-- Owner-only destructive data cleanup for Elory Dashboard.
-- This migration creates the PIN guard and RPCs only; it does not delete business data.

create extension if not exists pgcrypto with schema extensions;

create table if not exists public.owner_data_reset_settings (
    singleton boolean primary key default true check (singleton is true),
    owner_id uuid not null references auth.users(id) on delete restrict,
    pin_hash text,
    failed_attempts smallint not null default 0 check (failed_attempts between 0 and 5),
    locked_until timestamptz,
    updated_at timestamptz not null default now()
);

create table if not exists public.owner_data_reset_audit (
    id bigint generated always as identity primary key,
    owner_id uuid not null references auth.users(id) on delete restrict,
    scope text not null check (scope in ('orders', 'customers', 'coupons')),
    selected_ids text[],
    deleted_count integer not null default 0,
    order_sequence_reset boolean not null default false,
    created_at timestamptz not null default now()
);

alter table public.owner_data_reset_settings enable row level security;
alter table public.owner_data_reset_audit enable row level security;
revoke all on table public.owner_data_reset_settings from public, anon, authenticated;
revoke all on table public.owner_data_reset_audit from public, anon, authenticated;

do $$
declare
    v_owner_id uuid;
begin
    select sp.id
      into v_owner_id
      from public.staff_profiles sp
      join auth.users au on au.id = sp.id
     where lower(trim(coalesce(sp.role, ''))) = 'owner'
     order by au.created_at asc, sp.created_at asc, sp.id asc
     limit 1;

    if v_owner_id is null then
        raise exception 'Cannot configure Elory data reset: no owner account exists';
    end if;

    insert into public.owner_data_reset_settings(singleton, owner_id)
    values (true, v_owner_id)
    on conflict (singleton) do nothing;
end;
$$;

create or replace function public.admin_is_primary_owner()
returns boolean
language sql
stable
security definer
set search_path to ''
as $$
    select auth.uid() is not null
       and exists (
            select 1
              from public.owner_data_reset_settings s
             where s.singleton is true
               and s.owner_id = auth.uid()
       );
$$;

create or replace function public.admin_set_data_reset_pin(p_pin text)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
declare
    v_owner_id uuid;
begin
    select s.owner_id
      into v_owner_id
      from public.owner_data_reset_settings s
     where s.singleton is true;

    if auth.uid() is null or auth.uid() is distinct from v_owner_id then
        return jsonb_build_object('success', false, 'code', 'forbidden',
                                  'message', 'إعداد رمز الحذف متاح للمالك الأساسي فقط');
    end if;

    if coalesce(p_pin, '') !~ '^[0-9]{6}$' then
        return jsonb_build_object('success', false, 'code', 'invalid_pin',
                                  'message', 'رمز PIN يجب أن يتكون من 6 أرقام');
    end if;

    update public.owner_data_reset_settings
       set pin_hash = extensions.crypt(p_pin, extensions.gen_salt('bf', 12)),
           failed_attempts = 0,
           locked_until = null,
           updated_at = now()
     where singleton is true
       and owner_id = v_owner_id;

    return jsonb_build_object('success', true, 'message', 'تم حفظ رمز الحذف بأمان');
end;
$$;

create or replace function public.admin_delete_selected_data(
    p_pin text,
    p_scope text,
    p_ids text[] default null
)
returns jsonb
language plpgsql
security definer
set search_path to ''
as $$
declare
    v_owner_id uuid;
    v_pin_hash text;
    v_failed_attempts smallint;
    v_locked_until timestamptz;
    v_scope text := lower(trim(coalesce(p_scope, '')));
    v_deleted integer := 0;
    v_order_sequence_reset boolean := false;
begin
    select s.owner_id, s.pin_hash, s.failed_attempts, s.locked_until
      into v_owner_id, v_pin_hash, v_failed_attempts, v_locked_until
      from public.owner_data_reset_settings s
     where s.singleton is true
     for update;

    if auth.uid() is null or auth.uid() is distinct from v_owner_id then
        return jsonb_build_object('success', false, 'code', 'forbidden',
                                  'message', 'حذف البيانات متاح للمالك الأساسي فقط');
    end if;

    if v_pin_hash is null then
        return jsonb_build_object('success', false, 'code', 'pin_not_configured',
                                  'message', 'يجب إعداد رمز PIN من 6 أرقام أولاً');
    end if;

    if v_locked_until is not null and v_locked_until > now() then
        return jsonb_build_object('success', false, 'code', 'pin_locked',
                                  'message', 'تم إيقاف المحاولة مؤقتًا بسبب تكرار الرمز الخاطئ');
    end if;

    if coalesce(p_pin, '') !~ '^[0-9]{6}$'
       or extensions.crypt(p_pin, v_pin_hash) is distinct from v_pin_hash then
        v_failed_attempts := least(coalesce(v_failed_attempts, 0) + 1, 5);
        update public.owner_data_reset_settings
           set failed_attempts = v_failed_attempts,
               locked_until = case
                   when v_failed_attempts >= 5 then now() + interval '15 minutes'
                   else null
               end,
               updated_at = now()
         where singleton is true;

        return jsonb_build_object(
            'success', false,
            'code', case when v_failed_attempts >= 5 then 'pin_locked' else 'invalid_pin' end,
            'attempts_remaining', greatest(0, 5 - v_failed_attempts),
            'message', case
                when v_failed_attempts >= 5 then 'تم إيقاف المحاولات لمدة 15 دقيقة'
                else 'رمز PIN غير صحيح'
            end
        );
    end if;

    update public.owner_data_reset_settings
       set failed_attempts = 0,
           locked_until = null,
           updated_at = now()
     where singleton is true;

    if v_scope not in ('orders', 'customers', 'coupons') then
        return jsonb_build_object('success', false, 'code', 'invalid_scope',
                                  'message', 'نوع البيانات المطلوب حذفه غير مسموح');
    end if;

    if p_ids is not null and cardinality(p_ids) = 0 then
        return jsonb_build_object('success', false, 'code', 'empty_selection',
                                  'message', 'لم يتم تحديد أي سجلات للحذف');
    end if;

    if v_scope = 'orders' then
        -- Serialize order creation with a full reset so the next order number is deterministic.
        lock table public.orders in access exclusive mode;

        delete from public.orders o
         where p_ids is null
            or o.id::text = any(p_ids);
        get diagnostics v_deleted = row_count;

        if not exists (select 1 from public.orders) then
            alter sequence public.elora_order_number_seq restart with 1;
            v_order_sequence_reset := true;
        end if;

        -- Redemptions cascade with orders; recompute denormalized coupon counters.
        update public.coupons c
           set used_count = (
               select count(*)::integer
                 from public.coupon_redemptions cr
                where cr.coupon_id = c.id
           );
    elsif v_scope = 'customers' then
        -- Customer profile rows only. Auth accounts and order history are preserved.
        delete from public.customers c
         where p_ids is null
            or c.id::text = any(p_ids);
        get diagnostics v_deleted = row_count;
    elsif v_scope = 'coupons' then
        -- Remove redemption rows first because coupon_id uses ON DELETE RESTRICT.
        delete from public.coupon_redemptions cr
         where p_ids is null
            or cr.coupon_id::text = any(p_ids);

        delete from public.coupons c
         where p_ids is null
            or c.id::text = any(p_ids);
        get diagnostics v_deleted = row_count;
    end if;

    insert into public.owner_data_reset_audit(
        owner_id, scope, selected_ids, deleted_count, order_sequence_reset
    )
    values (v_owner_id, v_scope, p_ids, v_deleted, v_order_sequence_reset);

    return jsonb_build_object(
        'success', true,
        'scope', v_scope,
        'deleted_count', v_deleted,
        'order_sequence_reset', v_order_sequence_reset,
        'message', case v_scope
            when 'orders' then 'تم حذف الطلبات المحددة بنجاح'
            when 'customers' then 'تم حذف العملاء المحددين بنجاح'
            else 'تم حذف الكوبونات المحددة بنجاح'
        end
    );
end;
$$;

revoke all on function public.admin_is_primary_owner() from public, anon;
revoke all on function public.admin_set_data_reset_pin(text) from public, anon;
revoke all on function public.admin_delete_selected_data(text, text, text[]) from public, anon;

grant execute on function public.admin_is_primary_owner() to authenticated;
grant execute on function public.admin_set_data_reset_pin(text) to authenticated;
grant execute on function public.admin_delete_selected_data(text, text, text[]) to authenticated;

comment on table public.owner_data_reset_settings is
    'PIN configuration for destructive customer/order/coupon cleanup; owner_id is fixed to the oldest owner account.';
comment on function public.admin_delete_selected_data(text, text, text[]) is
    'Owner-only PIN-protected deletion of selected orders, customer profiles, or coupons. Never deletes products, auth users, Prime subscriptions, or store settings.';
