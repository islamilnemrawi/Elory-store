-- Elory pre-launch hardening (zero-cost, isolated-test-first)
-- Do not apply to the production project until the migration and test suite pass
-- on an isolated database. No production rows are seeded by this migration.

ALTER TABLE public.orders
  ADD COLUMN IF NOT EXISTS idempotency_key uuid,
  ADD COLUMN IF NOT EXISTS idempotency_fingerprint text,
  ADD COLUMN IF NOT EXISTS inventory_reserved boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS inventory_released_at timestamptz;

-- A full UNIQUE index supports PostgREST ON CONFLICT semantics. NULL remains
-- allowed for historical/manual rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_idempotency_key
  ON public.orders (idempotency_key);

CREATE INDEX IF NOT EXISTS idx_products_active_created_id
  ON public.products (created_at DESC, id DESC)
  WHERE active IS TRUE;

CREATE INDEX IF NOT EXISTS idx_products_active_price_id
  ON public.products (price ASC, id ASC)
  WHERE active IS TRUE;

CREATE INDEX IF NOT EXISTS idx_orders_pending_payment_expiry
  ON public.orders (created_at)
  WHERE inventory_reserved IS TRUE
    AND payment_method IN ('card', 'vodafone_cash')
    AND status = 'جاري الدفع';

CREATE SCHEMA IF NOT EXISTS private;

-- Contains only the current pending inventory reservation for each order line.
CREATE TABLE IF NOT EXISTS private.elory_order_inventory_reservations (
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  item_index integer NOT NULL,
  product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE RESTRICT,
  quantity integer NOT NULL CHECK (quantity > 0),
  uses_variant_stock boolean NOT NULL DEFAULT false,
  variant_color text NOT NULL DEFAULT '',
  variant_size text NOT NULL DEFAULT '',
  restored_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (order_id, item_index)
);

CREATE INDEX IF NOT EXISTS idx_elory_inventory_reservations_pending
  ON private.elory_order_inventory_reservations (product_id, order_id)
  WHERE restored_at IS NULL;

ALTER TABLE private.elory_order_inventory_reservations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE private.elory_order_inventory_reservations FROM PUBLIC, anon, authenticated;

-- Paymob client secrets are stored only in a non-exposed schema.
CREATE TABLE IF NOT EXISTS private.elory_payment_sessions (
  idempotency_key uuid PRIMARY KEY,
  order_id uuid NOT NULL REFERENCES public.orders(id) ON DELETE CASCADE,
  payment_method text NOT NULL CHECK (payment_method IN ('card', 'vodafone_cash')),
  status text NOT NULL CHECK (status IN ('creating', 'ready', 'failed')),
  client_secret text,
  intention_id text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT elory_payment_session_ready_has_secret
    CHECK (status <> 'ready' OR NULLIF(client_secret, '') IS NOT NULL)
);

ALTER TABLE private.elory_payment_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE private.elory_payment_sessions FROM PUBLIC, anon, authenticated;

-- Reserve stock only after the existing server-side price/variant validation
-- trigger has accepted the order. The following UPDATE ... WHERE stock >= qty
-- is the atomic concurrency gate: a competing order waits, then sees the new
-- quantity and fails instead of overselling.
CREATE OR REPLACE FUNCTION public.elory_mark_new_order_inventory_reserved()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
  NEW.inventory_reserved := true;
  NEW.inventory_released_at := NULL;
  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS a0_elory_mark_new_order_inventory_reserved ON public.orders;
CREATE TRIGGER a0_elory_mark_new_order_inventory_reserved
BEFORE INSERT ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.elory_mark_new_order_inventory_reserved();

CREATE OR REPLACE FUNCTION public.elory_reserve_order_inventory()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_line record;
  v_product public.products%ROWTYPE;
  v_product_id text;
  v_qty_text text;
  v_qty integer;
  v_variant_index integer;
  v_variant jsonb;
  v_variant_stock_text text;
  v_uses_variant_stock boolean;
  v_color text;
  v_size text;
BEGIN
  IF NEW.inventory_reserved IS NOT TRUE THEN
    RETURN NEW;
  END IF;

  -- Consistent product lock ordering reduces deadlocks in multi-item orders.
  FOR v_line IN
    SELECT x.value AS item, x.ordinality
    FROM jsonb_array_elements(NEW.items) WITH ORDINALITY AS x(value, ordinality)
    ORDER BY COALESCE(x.value->>'product_id', x.value->>'id'), x.ordinality
  LOOP
    v_product_id := COALESCE(NULLIF(v_line.item->>'product_id', ''), NULLIF(v_line.item->>'id', ''));
    IF v_product_id IS NULL THEN
      RAISE EXCEPTION 'Elory inventory: item has no product id';
    END IF;

    v_qty_text := COALESCE(NULLIF(v_line.item->>'quantity', ''), NULLIF(v_line.item->>'qty', ''), '0');
    IF v_qty_text !~ '^[0-9]+$' THEN
      RAISE EXCEPTION 'Elory inventory: invalid quantity';
    END IF;
    v_qty := v_qty_text::integer;
    IF v_qty < 1 THEN
      RAISE EXCEPTION 'Elory inventory: quantity must be positive';
    END IF;

    SELECT p.*
      INTO v_product
      FROM public.products AS p
     WHERE p.id::text = v_product_id
     FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Elory inventory: product not found';
    END IF;

    v_color := COALESCE(v_line.item->>'color', '');
    v_size := COALESCE(v_line.item->>'size', '');
    v_variant_index := NULL;
    v_variant := NULL;
    v_variant_stock_text := NULL;
    v_uses_variant_stock := false;

    IF jsonb_typeof(v_product.variants) = 'array'
       AND jsonb_array_length(v_product.variants) > 0 THEN
      SELECT (variant.ordinality - 1)::integer
        INTO v_variant_index
        FROM jsonb_array_elements(v_product.variants) WITH ORDINALITY AS variant(value, ordinality)
       WHERE COALESCE(
               variant.value->>'color_name',
               variant.value->'color'->>'name',
               variant.value->>'color',
               ''
             ) = v_color
         AND COALESCE(
               variant.value->>'size',
               variant.value->>'size_name',
               ''
             ) = v_size
       ORDER BY variant.ordinality
       LIMIT 1;

      IF v_variant_index IS NOT NULL THEN
        v_variant := v_product.variants -> v_variant_index;
        v_variant_stock_text := NULLIF(v_variant->>'stock', '');
      END IF;
    END IF;

    IF v_variant_index IS NOT NULL
       AND v_variant_stock_text ~ '^[0-9]+$' THEN
      UPDATE public.products AS p
         SET variants = jsonb_set(
           p.variants,
           ARRAY[v_variant_index::text, 'stock'],
           to_jsonb((p.variants -> v_variant_index ->> 'stock')::integer - v_qty),
           true
         )
       WHERE p.id = v_product.id
         AND CASE
               WHEN (p.variants -> v_variant_index ->> 'stock') ~ '^[0-9]+$'
                 THEN (p.variants -> v_variant_index ->> 'stock')::integer >= v_qty
               ELSE false
             END;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'الكمية المطلوبة من هذا اللون أو المقاس لم تعد متاحة';
      END IF;
      v_uses_variant_stock := true;
    ELSE
      UPDATE public.products AS p
         SET stock = p.stock - v_qty
       WHERE p.id = v_product.id
         AND p.stock >= v_qty;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'الكمية المطلوبة من أحد المنتجات لم تعد متاحة';
      END IF;
    END IF;

    INSERT INTO private.elory_order_inventory_reservations (
      order_id, item_index, product_id, quantity,
      uses_variant_stock, variant_color, variant_size
    )
    VALUES (
      NEW.id, v_line.ordinality::integer, v_product.id, v_qty,
      v_uses_variant_stock, v_color, v_size
    );
  END LOOP;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS aaa_elory_reserve_order_inventory ON public.orders;
CREATE TRIGGER aaa_elory_reserve_order_inventory
AFTER INSERT ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.elory_reserve_order_inventory();

-- Restore from the exact reserved bucket. If a reserved variant was removed
-- from the product, cancellation fails loudly instead of crediting the wrong
-- stock bucket or silently losing inventory.
CREATE OR REPLACE FUNCTION private.elory_restore_order_inventory(p_order_id uuid)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_reservation private.elory_order_inventory_reservations%ROWTYPE;
  v_product public.products%ROWTYPE;
  v_variant_index integer;
  v_stock_text text;
BEGIN
  FOR v_reservation IN
    SELECT r.*
      FROM private.elory_order_inventory_reservations AS r
     WHERE r.order_id = p_order_id
       AND r.restored_at IS NULL
     ORDER BY r.product_id, r.item_index
     FOR UPDATE
  LOOP
    SELECT p.*
      INTO v_product
      FROM public.products AS p
     WHERE p.id = v_reservation.product_id
     FOR UPDATE;

    IF NOT FOUND THEN
      RAISE EXCEPTION 'Elory inventory restore: product % no longer exists', v_reservation.product_id;
    END IF;

    IF v_reservation.uses_variant_stock THEN
      SELECT (variant.ordinality - 1)::integer
        INTO v_variant_index
        FROM jsonb_array_elements(v_product.variants) WITH ORDINALITY AS variant(value, ordinality)
       WHERE COALESCE(
               variant.value->>'color_name',
               variant.value->'color'->>'name',
               variant.value->>'color',
               ''
             ) = v_reservation.variant_color
         AND COALESCE(
               variant.value->>'size',
               variant.value->>'size_name',
               ''
             ) = v_reservation.variant_size
       ORDER BY variant.ordinality
       LIMIT 1;

      IF v_variant_index IS NULL THEN
        RAISE EXCEPTION 'Elory inventory restore: reserved variant for product % is missing; restore the variant before cancelling this order', v_reservation.product_id;
      END IF;

      v_stock_text := NULLIF(v_product.variants -> v_variant_index ->> 'stock', '');
      IF v_stock_text !~ '^[0-9]+$' THEN
        RAISE EXCEPTION 'Elory inventory restore: variant stock for product % is invalid', v_reservation.product_id;
      END IF;

      UPDATE public.products AS p
         SET variants = jsonb_set(
           p.variants,
           ARRAY[v_variant_index::text, 'stock'],
           to_jsonb((p.variants -> v_variant_index ->> 'stock')::integer + v_reservation.quantity),
           true
         )
       WHERE p.id = v_reservation.product_id;
    ELSE
      UPDATE public.products
         SET stock = stock + v_reservation.quantity
       WHERE id = v_reservation.product_id;
    END IF;

    UPDATE private.elory_order_inventory_reservations
       SET restored_at = now()
     WHERE order_id = v_reservation.order_id
       AND item_index = v_reservation.item_index
       AND restored_at IS NULL;
  END LOOP;
END;
$function$;

CREATE OR REPLACE FUNCTION public.elory_manage_order_inventory()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_status text;
BEGIN
  IF OLD.inventory_reserved IS TRUE
     AND NEW.items IS DISTINCT FROM OLD.items THEN
    RAISE EXCEPTION 'لا يمكن تغيير منتجات الطلب بعد حجز المخزون؛ ألغِ الطلب وأنشئ طلبًا جديدًا';
  END IF;

  v_status := lower(trim(COALESCE(NEW.status, '')));
  IF OLD.inventory_reserved IS TRUE
     AND v_status = ANY (ARRAY[
       lower('فشل الدفع'),
       lower('فشل إنشاء الدفع'),
       lower('انتهى وقت الدفع'),
       lower('ملغي'),
       lower('ملغى'),
       'cancelled',
       'canceled',
       'rejected',
       'failed'
     ]) THEN
    PERFORM private.elory_restore_order_inventory(OLD.id);
    NEW.inventory_reserved := false;
    NEW.inventory_released_at := now();
  ELSE
    NEW.inventory_reserved := OLD.inventory_reserved;
    NEW.inventory_released_at := OLD.inventory_released_at;
  END IF;

  RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS a0_elory_manage_order_inventory ON public.orders;
CREATE TRIGGER a0_elory_manage_order_inventory
BEFORE UPDATE OF items, status, inventory_reserved, inventory_released_at ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.elory_manage_order_inventory();

CREATE OR REPLACE FUNCTION public.elory_restore_inventory_before_order_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
BEGIN
  IF OLD.inventory_reserved IS TRUE THEN
    PERFORM private.elory_restore_order_inventory(OLD.id);
  END IF;
  RETURN OLD;
END;
$function$;

DROP TRIGGER IF EXISTS a0_elory_restore_inventory_before_order_delete ON public.orders;
CREATE TRIGGER a0_elory_restore_inventory_before_order_delete
BEFORE DELETE ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.elory_restore_inventory_before_order_delete();

CREATE OR REPLACE FUNCTION public.elory_release_expired_inventory_reservations()
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_released integer := 0;
BEGIN
  UPDATE public.orders
     SET status = 'انتهى وقت الدفع'
   WHERE inventory_reserved IS TRUE
     AND payment_method IN ('card', 'vodafone_cash')
     AND status = 'جاري الدفع'
     AND created_at < now() - interval '65 minutes';

  GET DIAGNOSTICS v_released = ROW_COUNT;
  RETURN v_released;
END;
$function$;

-- One database transaction and advisory lock per checkout key. This checks for
-- an existing order BEFORE running its BEFORE/AFTER triggers, so a replay never
-- re-validates depleted stock and never reserves the same inventory twice.
CREATE OR REPLACE FUNCTION public.elory_create_order_once(
  p_order_payload jsonb,
  p_idempotency_key uuid
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_order public.orders%ROWTYPE;
  v_fingerprint text;
  v_payment_method text;
BEGIN
  IF p_idempotency_key IS NULL OR jsonb_typeof(p_order_payload) <> 'object' THEN
    RAISE EXCEPTION 'Invalid order idempotency input';
  END IF;

  v_payment_method := lower(trim(COALESCE(p_order_payload->>'payment_method', '')));
  IF v_payment_method NOT IN ('card', 'vodafone_cash', 'cash_on_delivery') THEN
    RAISE EXCEPTION 'Unsupported order payment method';
  END IF;

  v_fingerprint := encode(
    extensions.digest(
      convert_to(
        (p_order_payload - 'subtotal' - 'shipping_cost' - 'total' - 'profit' - 'status')::text,
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  );

  PERFORM pg_catalog.pg_advisory_xact_lock(
    pg_catalog.hashtextextended(p_idempotency_key::text, 0)
  );

  SELECT o.*
    INTO v_order
    FROM public.orders AS o
   WHERE o.idempotency_key = p_idempotency_key
   LIMIT 1;

  IF FOUND THEN
    IF v_order.idempotency_fingerprint IS DISTINCT FROM v_fingerprint
       OR lower(trim(COALESCE(v_order.payment_method, ''))) <> v_payment_method THEN
      RAISE EXCEPTION 'Idempotency key was reused with different order content';
    END IF;
    RETURN jsonb_build_object('ok', true, 'replayed', true, 'order', to_jsonb(v_order));
  END IF;

  INSERT INTO public.orders (
    idempotency_key,
    idempotency_fingerprint,
    user_id,
    customer_user_id,
    customer_access_token,
    customer_name,
    phone,
    governorate,
    center,
    address,
    notes,
    items,
    subtotal,
    shipping_cost,
    total,
    payment_method,
    status,
    prime,
    prime_requested,
    coupon_code,
    coupon_discount,
    coupon_free_shipping,
    prime_discount,
    prime_free_shipping,
    profit
  )
  VALUES (
    p_idempotency_key,
    v_fingerprint,
    NULLIF(p_order_payload->>'user_id', '')::uuid,
    NULLIF(p_order_payload->>'user_id', '')::uuid,
    NULLIF(p_order_payload->>'customer_access_token', ''),
    COALESCE(NULLIF(p_order_payload->>'customer_name', ''), 'Elory Customer'),
    NULLIF(p_order_payload->>'phone', ''),
    NULLIF(p_order_payload->>'governorate', ''),
    NULLIF(p_order_payload->>'center', ''),
    NULLIF(p_order_payload->>'address', ''),
    NULLIF(p_order_payload->>'notes', ''),
    COALESCE(p_order_payload->'items', '[]'::jsonb),
    COALESCE(NULLIF(p_order_payload->>'subtotal', '')::numeric, 0),
    COALESCE(NULLIF(p_order_payload->>'shipping_cost', '')::numeric, 0),
    COALESCE(NULLIF(p_order_payload->>'total', '')::numeric, 0),
    v_payment_method,
    CASE WHEN v_payment_method = 'cash_on_delivery' THEN 'طلب جديد' ELSE 'جاري الدفع' END,
    COALESCE(NULLIF(p_order_payload->>'prime', '')::boolean, false),
    COALESCE(NULLIF(p_order_payload->>'prime_requested', '')::boolean, false),
    NULLIF(p_order_payload->>'coupon_code', ''),
    COALESCE(NULLIF(p_order_payload->>'coupon_discount', '')::numeric, 0),
    COALESCE(NULLIF(p_order_payload->>'coupon_free_shipping', '')::boolean, false),
    COALESCE(NULLIF(p_order_payload->>'prime_discount', '')::numeric, 0),
    COALESCE(NULLIF(p_order_payload->>'prime_free_shipping', '')::boolean, false),
    COALESCE(NULLIF(p_order_payload->>'profit', '')::numeric, 0)
  )
  RETURNING * INTO v_order;

  RETURN jsonb_build_object('ok', true, 'replayed', false, 'order', to_jsonb(v_order));
END;
$function$;

-- A pending session is claimed before calling Paymob. A retry returns the
-- same client secret once ready; concurrent calls receive "in_progress".
-- An ambiguous old "creating" state is never retried automatically, because
-- doing so could create a second chargeable intention.
CREATE OR REPLACE FUNCTION public.elory_claim_order_payment_session(
  p_idempotency_key uuid,
  p_order_id uuid,
  p_payment_method text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_session private.elory_payment_sessions%ROWTYPE;
  v_inserted integer := 0;
BEGIN
  IF p_idempotency_key IS NULL OR p_order_id IS NULL
     OR p_payment_method NOT IN ('card', 'vodafone_cash') THEN
    RAISE EXCEPTION 'Invalid payment session input';
  END IF;

  INSERT INTO private.elory_payment_sessions (
    idempotency_key, order_id, payment_method, status
  )
  VALUES (p_idempotency_key, p_order_id, p_payment_method, 'creating')
  ON CONFLICT (idempotency_key) DO NOTHING;

  GET DIAGNOSTICS v_inserted = ROW_COUNT;

  SELECT s.*
    INTO v_session
    FROM private.elory_payment_sessions AS s
   WHERE s.idempotency_key = p_idempotency_key
   FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Payment session could not be created';
  END IF;

  IF v_session.order_id <> p_order_id
     OR v_session.payment_method <> p_payment_method THEN
    RAISE EXCEPTION 'Idempotency key is already bound to a different order or payment method';
  END IF;

  IF v_session.status = 'ready' AND NULLIF(v_session.client_secret, '') IS NOT NULL THEN
    RETURN jsonb_build_object(
      'status', 'ready',
      'client_secret', v_session.client_secret,
      'intention_id', v_session.intention_id
    );
  END IF;

  IF v_inserted = 1 THEN
    RETURN jsonb_build_object('status', 'claimed');
  END IF;

  IF v_session.status = 'creating' THEN
    IF v_session.updated_at > now() - interval '5 minutes' THEN
      RETURN jsonb_build_object('status', 'in_progress');
    END IF;
    RETURN jsonb_build_object('status', 'needs_review');
  END IF;

  -- A previous request failed after this order already reserved stock.
  -- Require a new checkout key/order rather than silently creating a new charge.
  IF v_session.status = 'failed' THEN
    RETURN jsonb_build_object('status', 'failed');
  END IF;

  RETURN jsonb_build_object('status', 'needs_review');
END;
$function$;

CREATE OR REPLACE FUNCTION public.elory_complete_order_payment_session(
  p_idempotency_key uuid,
  p_client_secret text,
  p_intention_id text
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_updated integer := 0;
BEGIN
  IF p_idempotency_key IS NULL OR NULLIF(trim(p_client_secret), '') IS NULL THEN
    RETURN false;
  END IF;

  UPDATE private.elory_payment_sessions
     SET status = 'ready',
         client_secret = trim(p_client_secret),
         intention_id = NULLIF(trim(p_intention_id), ''),
         updated_at = now()
   WHERE idempotency_key = p_idempotency_key
     AND status = 'creating';

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  IF v_updated = 1 THEN RETURN true; END IF;

  RETURN EXISTS (
    SELECT 1
      FROM private.elory_payment_sessions
     WHERE idempotency_key = p_idempotency_key
       AND status = 'ready'
       AND client_secret = trim(p_client_secret)
  );
END;
$function$;

CREATE OR REPLACE FUNCTION public.elory_fail_order_payment_session(p_idempotency_key uuid)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $function$
DECLARE
  v_updated integer := 0;
BEGIN
  UPDATE private.elory_payment_sessions
     SET status = 'failed',
         client_secret = NULL,
         intention_id = NULL,
         updated_at = now()
   WHERE idempotency_key = p_idempotency_key
     AND status = 'creating';

  GET DIAGNOSTICS v_updated = ROW_COUNT;
  RETURN v_updated = 1;
END;
$function$;

REVOKE ALL ON FUNCTION public.elory_release_expired_inventory_reservations() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_create_order_once(jsonb, uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_claim_order_payment_session(uuid, uuid, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_complete_order_payment_session(uuid, text, text) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_fail_order_payment_session(uuid) FROM PUBLIC, anon, authenticated;

GRANT EXECUTE ON FUNCTION public.elory_release_expired_inventory_reservations() TO service_role;
GRANT EXECUTE ON FUNCTION public.elory_create_order_once(jsonb, uuid) TO service_role;
GRANT EXECUTE ON FUNCTION public.elory_claim_order_payment_session(uuid, uuid, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.elory_complete_order_payment_session(uuid, text, text) TO service_role;
GRANT EXECUTE ON FUNCTION public.elory_fail_order_payment_session(uuid) TO service_role;

-- pg_trgm accelerates contains-searches when the extension is available.
DO $$
DECLARE
  v_trgm_schema text;
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm') THEN
    EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions';
  END IF;

  SELECT n.nspname
    INTO v_trgm_schema
    FROM pg_extension e
    JOIN pg_namespace n ON n.oid = e.extnamespace
   WHERE e.extname = 'pg_trgm';

  IF v_trgm_schema IS NOT NULL THEN
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_products_active_name_trgm ON public.products USING gin (name %I.gin_trgm_ops) WHERE active IS TRUE',
      v_trgm_schema
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_products_active_category_trgm ON public.products USING gin (category %I.gin_trgm_ops) WHERE active IS TRUE',
      v_trgm_schema
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_products_active_code_trgm ON public.products USING gin (code %I.gin_trgm_ops) WHERE active IS TRUE',
      v_trgm_schema
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS idx_products_active_sku_trgm ON public.products USING gin (sku %I.gin_trgm_ops) WHERE active IS TRUE',
      v_trgm_schema
    );
  END IF;
END;
$$;

REVOKE ALL ON FUNCTION public.elory_mark_new_order_inventory_reserved() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_reserve_order_inventory() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION private.elory_restore_order_inventory(uuid) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_manage_order_inventory() FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.elory_restore_inventory_before_order_delete() FROM PUBLIC, anon, authenticated;

COMMENT ON COLUMN public.orders.idempotency_key IS
  'Unique checkout key used to make COD and Paymob order creation idempotent.';
COMMENT ON COLUMN public.orders.idempotency_fingerprint IS
  'Hash of the client order intent used to reject reuse of an idempotency key for different cart content.';
COMMENT ON COLUMN public.orders.inventory_reserved IS
  'True while the order owns a transactional reservation of product or variant stock.';
COMMENT ON COLUMN public.orders.inventory_released_at IS
  'Timestamp when a failed, expired, cancelled or deleted order returned its reserved stock.';
