-- Elory customer-facing order codes.
-- The internal orders.order_number identity/sequence is intentionally untouched.
begin;

alter table public.orders
  add column if not exists customer_order_code text;

create or replace function private.generate_customer_order_code()
returns text
language plpgsql
volatile
security definer
set search_path = ''
as $function$
declare
  v_alphabet constant text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  v_random bytea;
  v_code text;
  v_pair bigint;
  v_byte_index integer;
  v_bit_offset integer;
  v_value integer;
  v_attempt integer;
  i integer;
begin
  for v_attempt in 1..10 loop
    -- 9 random bytes provide 72 bits; 13 Base32 characters use 65 bits.
    v_random := extensions.gen_random_bytes(9);
    v_code := '';

    for i in 0..12 loop
      v_byte_index := (i * 5) / 8;
      v_bit_offset := (i * 5) % 8;
      v_pair :=
        (get_byte(v_random, v_byte_index)::bigint << 8)
        | get_byte(v_random, v_byte_index + 1)::bigint;
      v_value := ((v_pair >> (11 - v_bit_offset)) & 31)::integer;
      v_code := v_code || substr(v_alphabet, v_value + 1, 1);
    end loop;

    v_code := 'EL-' || v_code;
    if not exists (
      select 1
      from public.orders as o
      where o.customer_order_code = v_code
    ) then
      return v_code;
    end if;
  end loop;

  raise exception 'Unable to generate a unique Elory customer order code';
end;
$function$;

revoke all on function private.generate_customer_order_code() from public, anon, authenticated;

-- Backfill existing rows while preserving every internal order_number value.
update public.orders
set customer_order_code = private.generate_customer_order_code()
where customer_order_code is null
   or btrim(customer_order_code) = '';

create unique index if not exists orders_customer_order_code_key
  on public.orders (customer_order_code);

alter table public.orders
  alter column customer_order_code set not null;

create or replace function private.assign_customer_order_code()
returns trigger
language plpgsql
security definer
set search_path = ''
as $function$
begin
  if tg_op = 'INSERT' then
    -- Always generate on the server; clients cannot choose or overwrite a code.
    new.customer_order_code := private.generate_customer_order_code();
  else
    -- The code is immutable after the order is created.
    new.customer_order_code := old.customer_order_code;
  end if;

  return new;
end;
$function$;

revoke all on function private.assign_customer_order_code() from public, anon, authenticated;

drop trigger if exists trg_elory_assign_customer_order_code on public.orders;
create trigger trg_elory_assign_customer_order_code
before insert or update of customer_order_code
on public.orders
for each row
execute function private.assign_customer_order_code();

comment on column public.orders.customer_order_code is
  'Immutable random customer-facing reference; internal order_number remains the store sequence.';

-- Preserve the current ownership/token restrictions and only add the customer-facing code.
drop function if exists public.get_customer_orders(text, text);

create function public.get_customer_orders(
  p_access_token text default null,
  p_phone text default null
)
returns table(
  id uuid,
  order_number text,
  user_id uuid,
  created_at timestamp with time zone,
  status text,
  items jsonb,
  shipping_cost numeric,
  total numeric,
  governorate text,
  center text,
  customer_order_code text
)
language sql
stable
security definer
set search_path = ''
as $function$
  select
    o.id,
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text) as order_number,
    o.user_id,
    o.created_at,
    o.status,
    case
      when jsonb_typeof(o.items) = 'array' then
        coalesce((
          select jsonb_agg(
            x.item
              - 'wholesale_price'
              - 'product_code'
              - 'product_image'
              - 'product_name'
              - 'wholesalePrice'
              - 'productCode'
              - 'productImage'
              - 'productName'
            order by x.ordinality
          )
          from jsonb_array_elements(o.items) with ordinality as x(item, ordinality)
        ), '[]'::jsonb)
      else coalesce(o.items, '[]'::jsonb)
    end as items,
    coalesce(o.shipping_cost, 0) as shipping_cost,
    coalesce(o.total, 0) as total,
    o.governorate,
    o.center,
    o.customer_order_code
  from public.orders as o
  where (
    (auth.uid() is not null and o.user_id = auth.uid())
    or (
      p_access_token is not null
      and length(trim(p_access_token)) >= 24
      and o.customer_access_token = trim(p_access_token)
    )
  )
  order by o.created_at desc;
$function$;

revoke all on function public.get_customer_orders(text, text) from public;
grant execute on function public.get_customer_orders(text, text) to anon, authenticated;

commit;
