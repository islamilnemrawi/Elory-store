-- Elory order inventory lifecycle and customer order data minimization.
-- Forward-only migration. No existing orders or product stock are backfilled or modified.

CREATE TABLE IF NOT EXISTS private.elory_order_inventory_state (
  order_id uuid PRIMARY KEY REFERENCES public.orders(id) ON DELETE CASCADE,
  deducted_at timestamptz,
  restored_at timestamptz,
  CONSTRAINT elory_order_inventory_state_timestamps_check
    CHECK (restored_at IS NULL OR deducted_at IS NOT NULL)
);

ALTER TABLE private.elory_order_inventory_state ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE private.elory_order_inventory_state FROM PUBLIC, anon, authenticated;

CREATE OR REPLACE FUNCTION private.elory_sync_order_inventory()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_old_confirmed boolean := false;
  v_new_confirmed boolean := false;
  v_new_cancelled boolean := false;
  v_state private.elory_order_inventory_state%ROWTYPE;
  v_item record;
BEGIN
  IF TG_OP = 'UPDATE' THEN
    v_old_confirmed := lower(btrim(coalesce(OLD.status, ''))) IN (
      'طلب جديد', 'تم تأكيد الطلب', 'تم التأكيد',
      'قيد التجهيز', 'جاري التجهيز', 'جاري التحضير',
      'جاري الشحن', 'تم الشحن', 'تم التسليم', 'تم التوصيل'
    );
  END IF;

  v_new_confirmed := lower(btrim(coalesce(NEW.status, ''))) IN (
    'طلب جديد', 'تم تأكيد الطلب', 'تم التأكيد',
    'قيد التجهيز', 'جاري التجهيز', 'جاري التحضير',
    'جاري الشحن', 'تم الشحن', 'تم التسليم', 'تم التوصيل'
  );
  v_new_cancelled := lower(btrim(coalesce(NEW.status, ''))) IN (
    'ملغي', 'ملغى', 'cancelled', 'canceled'
  );

  INSERT INTO private.elory_order_inventory_state(order_id)
  VALUES (NEW.id)
  ON CONFLICT (order_id) DO NOTHING;

  SELECT *
    INTO v_state
    FROM private.elory_order_inventory_state
   WHERE order_id = NEW.id
   FOR UPDATE;

  -- Deduct only when an order first enters a confirmed fulfillment state.
  -- A cancelled order may be confirmed again; in that case it is deducted again.
  IF v_new_confirmed
     AND (NOT v_old_confirmed OR v_state.restored_at IS NOT NULL)
     AND (v_state.deducted_at IS NULL OR v_state.restored_at IS NOT NULL) THEN

    FOR v_item IN
      SELECT
        coalesce(nullif(item->>'product_id', ''), nullif(item->>'id', ''))::uuid AS product_id,
        sum(coalesce(nullif(item->>'quantity', ''), nullif(item->>'qty', ''), '0')::integer)::integer AS quantity
      FROM jsonb_array_elements(NEW.items) AS entries(item)
      GROUP BY 1
      ORDER BY 1
    LOOP
      UPDATE public.products AS p
         SET stock = p.stock - v_item.quantity
       WHERE p.id = v_item.product_id
         AND p.stock >= v_item.quantity;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'المخزون غير كافٍ لتأكيد الطلب. راجع كميات المنتجات ثم حاول مرة أخرى';
      END IF;
    END LOOP;

    UPDATE private.elory_order_inventory_state
       SET deducted_at = clock_timestamp(),
           restored_at = NULL
     WHERE order_id = NEW.id;

  -- Restore exactly once when a previously confirmed order is cancelled.
  ELSIF v_new_cancelled
        AND v_state.deducted_at IS NOT NULL
        AND v_state.restored_at IS NULL THEN

    FOR v_item IN
      SELECT
        coalesce(nullif(item->>'product_id', ''), nullif(item->>'id', ''))::uuid AS product_id,
        sum(coalesce(nullif(item->>'quantity', ''), nullif(item->>'qty', ''), '0')::integer)::integer AS quantity
      FROM jsonb_array_elements(OLD.items) AS entries(item)
      GROUP BY 1
      ORDER BY 1
    LOOP
      UPDATE public.products AS p
         SET stock = p.stock + v_item.quantity
       WHERE p.id = v_item.product_id;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'تعذر إعادة المخزون لأن أحد المنتجات لم يعد موجودًا. لا يمكن إتمام الإلغاء قبل مراجعة المنتج';
      END IF;
    END LOOP;

    UPDATE private.elory_order_inventory_state
       SET restored_at = clock_timestamp()
     WHERE order_id = NEW.id;
  END IF;

  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.elory_sync_order_inventory() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS zz_elory_validate_order_totals ON public.orders;
CREATE TRIGGER zz_elory_validate_order_totals
BEFORE INSERT OR UPDATE OF items, coupon_code, governorate, center, prime_requested
ON public.orders
FOR EACH ROW
EXECUTE FUNCTION public.elory_validate_order_totals();

DROP TRIGGER IF EXISTS elory_sync_order_inventory_insert ON public.orders;
CREATE TRIGGER elory_sync_order_inventory_insert
AFTER INSERT ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.elory_sync_order_inventory();

DROP TRIGGER IF EXISTS elory_sync_order_inventory_status ON public.orders;
CREATE TRIGGER elory_sync_order_inventory_status
AFTER UPDATE OF status ON public.orders
FOR EACH ROW
WHEN (OLD.status IS DISTINCT FROM NEW.status)
EXECUTE FUNCTION private.elory_sync_order_inventory();

CREATE OR REPLACE FUNCTION private.elory_prevent_active_order_items_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM private.elory_order_inventory_state s
     WHERE s.order_id = OLD.id
       AND s.deducted_at IS NOT NULL
       AND s.restored_at IS NULL
  ) THEN
    RAISE EXCEPTION 'لا يمكن تعديل منتجات طلب تم خصم مخزونه. ألغِ الطلب أولًا ثم أنشئ طلبًا جديدًا';
  END IF;
  RETURN NEW;
END;
$function$;

REVOKE ALL ON FUNCTION private.elory_prevent_active_order_items_change() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS elory_prevent_active_order_items_change ON public.orders;
CREATE TRIGGER elory_prevent_active_order_items_change
BEFORE UPDATE OF items ON public.orders
FOR EACH ROW
WHEN (OLD.items IS DISTINCT FROM NEW.items)
EXECUTE FUNCTION private.elory_prevent_active_order_items_change();

CREATE OR REPLACE FUNCTION private.elory_prevent_product_delete_with_active_orders()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
BEGIN
  IF EXISTS (
    SELECT 1
      FROM public.orders o
      JOIN private.elory_order_inventory_state s ON s.order_id = o.id
      CROSS JOIN LATERAL jsonb_array_elements(o.items) AS entries(item)
     WHERE s.deducted_at IS NOT NULL
       AND s.restored_at IS NULL
       AND coalesce(nullif(entries.item->>'product_id', ''), nullif(entries.item->>'id', '')) = OLD.id::text
  ) THEN
    RAISE EXCEPTION 'لا يمكن حذف منتج مرتبط بطلب مؤكد لم يُلغَ بعد. ألغِ الطلب أولًا';
  END IF;
  RETURN OLD;
END;
$function$;

REVOKE ALL ON FUNCTION private.elory_prevent_product_delete_with_active_orders() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS elory_prevent_product_delete_with_active_orders ON public.products;
CREATE TRIGGER elory_prevent_product_delete_with_active_orders
BEFORE DELETE ON public.products
FOR EACH ROW
EXECUTE FUNCTION private.elory_prevent_product_delete_with_active_orders();

-- Keep both customer-order RPCs backward compatible while removing internal product data.
CREATE OR REPLACE FUNCTION public.get_customer_orders(
  p_access_token text DEFAULT NULL::text,
  p_phone text DEFAULT NULL::text
)
RETURNS TABLE(
  id uuid,
  order_number text,
  user_id uuid,
  created_at timestamptz,
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
SET search_path TO ''
AS $function$
  SELECT
    o.id,
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text),
    o.user_id,
    o.created_at,
    o.status,
    CASE
      WHEN jsonb_typeof(o.items) = 'array' THEN
        coalesce((
          SELECT jsonb_agg(
            x.item
              - 'code'
              - 'sku'
              - 'stock'
              - 'barcode'
              - 'product_sku'
              - 'product_stock'
              - 'wholesale_price'
              - 'product_code'
              - 'product_image'
              - 'product_name'
              - 'wholesalePrice'
              - 'productCode'
              - 'productImage'
              - 'productName'
              - 'cost_price'
            ORDER BY x.ordinality
          )
          FROM jsonb_array_elements(o.items) WITH ORDINALITY AS x(item, ordinality)
        ), '[]'::jsonb)
      ELSE coalesce(o.items, '[]'::jsonb)
    END,
    coalesce(o.shipping_cost, 0),
    coalesce(o.total, 0),
    o.governorate,
    o.center,
    o.customer_order_code
  FROM public.orders AS o
  WHERE (
    (auth.uid() IS NOT NULL AND o.user_id = auth.uid())
    OR (
      p_access_token IS NOT NULL
      AND length(btrim(p_access_token)) >= 24
      AND o.customer_access_token = btrim(p_access_token)
    )
  )
    AND lower(btrim(coalesce(o.status, ''))) NOT IN (
      'جاري الدفع', 'فشل الدفع', 'فشل إنشاء الدفع',
      'payment pending', 'pending payment', 'payment failed',
      'failed payment', 'failed to create payment'
    )
    AND NOT (
      lower(btrim(coalesce(o.payment_method, ''))) IN (
        'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
      )
      AND lower(btrim(coalesce(o.status, ''))) IN (
        'جديد', 'جاري التأكيد', 'pending', 'new'
      )
    )
  ORDER BY o.created_at DESC;
$function$;

CREATE OR REPLACE FUNCTION public.get_customer_orders_v2(
  p_access_token text DEFAULT NULL::text,
  p_phone text DEFAULT NULL::text
)
RETURNS TABLE(
  id uuid,
  order_number text,
  user_id uuid,
  created_at timestamptz,
  status text,
  payment_method text,
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
SET search_path TO ''
AS $function$
  SELECT
    o.id,
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text),
    o.user_id,
    o.created_at,
    o.status,
    o.payment_method,
    CASE
      WHEN jsonb_typeof(o.items) = 'array' THEN
        coalesce((
          SELECT jsonb_agg(
            x.item
              - 'code'
              - 'sku'
              - 'stock'
              - 'barcode'
              - 'product_sku'
              - 'product_stock'
              - 'wholesale_price'
              - 'product_code'
              - 'product_image'
              - 'product_name'
              - 'wholesalePrice'
              - 'productCode'
              - 'productImage'
              - 'productName'
              - 'cost_price'
            ORDER BY x.ordinality
          )
          FROM jsonb_array_elements(o.items) WITH ORDINALITY AS x(item, ordinality)
        ), '[]'::jsonb)
      ELSE coalesce(o.items, '[]'::jsonb)
    END,
    coalesce(o.shipping_cost, 0),
    coalesce(o.total, 0),
    o.governorate,
    o.center,
    o.customer_order_code
  FROM public.orders AS o
  WHERE (
    (auth.uid() IS NOT NULL AND o.user_id = auth.uid())
    OR (
      p_access_token IS NOT NULL
      AND length(btrim(p_access_token)) >= 24
      AND o.customer_access_token = btrim(p_access_token)
    )
  )
    AND lower(btrim(coalesce(o.status, ''))) NOT IN (
      'جاري الدفع', 'payment pending', 'pending payment'
    )
    AND NOT (
      lower(btrim(coalesce(o.payment_method, ''))) IN (
        'card', 'visa', 'paymob', 'vodafone_cash', 'vodafone cash'
      )
      AND lower(btrim(coalesce(o.status, ''))) IN (
        'جديد', 'جاري التأكيد', 'pending', 'new'
      )
    )
  ORDER BY o.created_at DESC;
$function$;

REVOKE ALL ON FUNCTION public.get_customer_orders(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_customer_orders(text, text) TO anon, authenticated;
REVOKE ALL ON FUNCTION public.get_customer_orders_v2(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_customer_orders_v2(text, text) TO anon, authenticated;

NOTIFY pgrst, 'reload schema';


-- Preserve inventory when an administrator permanently deletes an order.
-- The existing admin bulk-delete workflow remains available, but it cannot
-- silently erase the only record of stock already deducted for an active order.
CREATE OR REPLACE FUNCTION private.elory_restore_order_inventory_before_delete()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_state private.elory_order_inventory_state%ROWTYPE;
  v_item record;
BEGIN
  SELECT *
    INTO v_state
    FROM private.elory_order_inventory_state
   WHERE order_id = OLD.id
   FOR UPDATE;

  IF FOUND
     AND v_state.deducted_at IS NOT NULL
     AND v_state.restored_at IS NULL THEN
    FOR v_item IN
      SELECT
        coalesce(nullif(item->>'product_id', ''), nullif(item->>'id', ''))::uuid AS product_id,
        sum(coalesce(nullif(item->>'quantity', ''), nullif(item->>'qty', ''), '0')::integer)::integer AS quantity
      FROM jsonb_array_elements(OLD.items) AS entries(item)
      GROUP BY 1
      ORDER BY 1
    LOOP
      UPDATE public.products AS p
         SET stock = p.stock + v_item.quantity
       WHERE p.id = v_item.product_id;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'لا يمكن حذف الطلب لأن أحد منتجاته لم يعد موجودًا، وتعذرت إعادة المخزون';
      END IF;
    END LOOP;

    UPDATE private.elory_order_inventory_state
       SET restored_at = clock_timestamp()
     WHERE order_id = OLD.id;
  END IF;

  RETURN OLD;
END;
$function$;

REVOKE ALL ON FUNCTION private.elory_restore_order_inventory_before_delete() FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS elory_restore_order_inventory_before_delete ON public.orders;
CREATE TRIGGER elory_restore_order_inventory_before_delete
BEFORE DELETE ON public.orders
FOR EACH ROW
EXECUTE FUNCTION private.elory_restore_order_inventory_before_delete();
