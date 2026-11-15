-- Elory customer-facing order codes.
-- Keeps the existing orders.order_number identity and all order ownership rules unchanged.

ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS customer_order_code text;

CREATE OR REPLACE FUNCTION private.generate_customer_order_code()
RETURNS text
LANGUAGE plpgsql
VOLATILE
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_alphabet CONSTANT text := '0123456789ABCDEFGHJKMNPQRSTVWXYZ';
  v_random bytea;
  v_code text;
  v_pair bigint;
  v_byte_index integer;
  v_bit_offset integer;
  v_value integer;
  v_attempt integer;
  i integer;
BEGIN
  FOR v_attempt IN 1..10 LOOP
    -- 9 random bytes provide 72 bits; 13 Base32 characters use 65 bits.
    v_random := extensions.gen_random_bytes(9);
    v_code := '';

    FOR i IN 0..12 LOOP
      v_byte_index := (i * 5) / 8;
      v_bit_offset := (i * 5) % 8;
      v_pair :=
        (pg_catalog.get_byte(v_random, v_byte_index)::bigint << 8)
        | pg_catalog.get_byte(v_random, v_byte_index + 1)::bigint;
      v_value := ((v_pair >> (11 - v_bit_offset)) & 31)::integer;
      v_code := v_code || pg_catalog.substr(v_alphabet, v_value + 1, 1);
    END LOOP;

    v_code := 'EL-' || v_code;

    -- Serialize identical candidates across concurrent transactions before checking.
    PERFORM pg_catalog.pg_advisory_xact_lock(
      pg_catalog.hashtextextended(v_code, 0)
    );

    IF NOT EXISTS (
      SELECT 1
      FROM public.orders AS o
      WHERE o.customer_order_code = v_code
    ) THEN
      RETURN v_code;
    END IF;
  END LOOP;

  RAISE EXCEPTION 'Unable to generate a unique Elory customer order code';
END;
$function$;

REVOKE ALL ON FUNCTION private.generate_customer_order_code()
  FROM PUBLIC, anon, authenticated;

-- Backfill every existing order once. No order_number value is updated.
UPDATE public.orders
SET customer_order_code = private.generate_customer_order_code()
WHERE customer_order_code IS NULL
   OR pg_catalog.btrim(customer_order_code) = '';

CREATE UNIQUE INDEX IF NOT EXISTS orders_customer_order_code_key
  ON public.orders (customer_order_code);

ALTER TABLE public.orders
  ALTER COLUMN customer_order_code SET NOT NULL;

ALTER TABLE public.orders
  ADD CONSTRAINT orders_customer_order_code_format_check
  CHECK (customer_order_code ~ '^EL-[0-9A-HJKMNP-TV-Z]{13}$');

CREATE OR REPLACE FUNCTION private.assign_customer_order_code()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
  IF TG_OP = 'INSERT' THEN
    -- Always generate on the server; ignore any client-supplied code.
    NEW.customer_order_code := private.generate_customer_order_code();
  ELSE
    -- The code is immutable after the order is created.
    NEW.customer_order_code := OLD.customer_order_code;
  END IF;

  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.assign_customer_order_code()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS trg_elory_assign_customer_order_code
  ON public.orders;

CREATE TRIGGER trg_elory_assign_customer_order_code
BEFORE INSERT OR UPDATE OF customer_order_code
ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.assign_customer_order_code();

COMMENT ON COLUMN public.orders.customer_order_code IS
  'Immutable random customer-facing reference; internal order_number remains the store sequence.';

-- Recreate the existing customer-history RPC with the same security and ownership filters,
-- adding only the new customer_order_code return field.
DROP FUNCTION IF EXISTS public.get_customer_orders(text, text);

CREATE FUNCTION public.get_customer_orders(
  p_access_token text DEFAULT NULL,
  p_phone text DEFAULT NULL
)
RETURNS TABLE(
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
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = ''
AS $function$
  SELECT
    o.id,
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text) AS order_number,
    o.user_id,
    o.created_at,
    o.status,
    CASE
      WHEN jsonb_typeof(o.items) = 'array' THEN
        coalesce((
          SELECT jsonb_agg(
            x.item
              - 'wholesale_price'
              - 'product_code'
              - 'product_image'
              - 'product_name'
              - 'wholesalePrice'
              - 'productCode'
              - 'productImage'
              - 'productName'
            ORDER BY x.ordinality
          )
          FROM jsonb_array_elements(o.items) WITH ORDINALITY AS x(item, ordinality)
        ), '[]'::jsonb)
      ELSE coalesce(o.items, '[]'::jsonb)
    END AS items,
    coalesce(o.shipping_cost, 0) AS shipping_cost,
    coalesce(o.total, 0) AS total,
    o.governorate,
    o.center,
    o.customer_order_code
  FROM public.orders AS o
  WHERE (
    (auth.uid() IS NOT NULL AND o.user_id = auth.uid())
    OR (
      p_access_token IS NOT NULL
      AND length(trim(p_access_token)) >= 24
      AND o.customer_access_token = trim(p_access_token)
    )
  )
  ORDER BY o.created_at DESC;
$function$;

REVOKE ALL ON FUNCTION public.get_customer_orders(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_customer_orders(text, text) TO anon, authenticated;

NOTIFY pgrst, 'reload schema';
