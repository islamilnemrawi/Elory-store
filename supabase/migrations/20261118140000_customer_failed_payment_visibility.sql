-- Show explicit Paymob failures in the customer's order history.
-- Pending payment attempts remain hidden; failed attempts are visible as failed, never as paid.
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
    coalesce(to_jsonb(o)->>'order_number', to_jsonb(o)->>'order_code', o.id::text) AS order_number,
    o.user_id,
    o.created_at,
    o.status,
    o.payment_method,
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
      AND length(btrim(p_access_token)) >= 24
      AND o.customer_access_token = btrim(p_access_token)
    )
  )
    -- Hide only live/pending payment attempts. Keep explicit failure records visible.
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

REVOKE ALL ON FUNCTION public.get_customer_orders_v2(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_customer_orders_v2(text, text) TO anon, authenticated;
NOTIFY pgrst, 'reload schema';
