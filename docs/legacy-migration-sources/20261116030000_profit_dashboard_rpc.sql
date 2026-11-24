BEGIN;

CREATE OR REPLACE FUNCTION public.admin_get_profit_dashboard(p_days integer DEFAULT 90)
RETURNS jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $function$
DECLARE
  v_days integer := greatest(1, least(coalesce(p_days, 90), 3650));
  v_from timestamptz;
  v_result jsonb;
BEGIN
  IF NOT public.has_staff_permission('analytics.profit') THEN
    RAISE EXCEPTION 'ليس لديك صلاحية مشاهدة تقارير الأرباح'
      USING ERRCODE = '42501';
  END IF;

  v_from := now() - make_interval(days => v_days);

  WITH scoped_orders AS (
    SELECT o.*
    FROM public.orders o
    WHERE o.created_at >= v_from
      AND o.created_at <= now()
  ),
  summary AS (
    SELECT
      count(*) FILTER (
        WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
      )::integer AS delivered_orders,
      coalesce(sum(total) FILTER (
        WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
      ), 0)::numeric AS delivered_sales,
      coalesce(sum(profit) FILTER (
        WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
      ), 0)::numeric AS product_gross_margin,
      count(*) FILTER (
        WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
          AND profit IS NULL
      )::integer AS missing_profit_orders,
      count(*) FILTER (
        WHERE trim(coalesce(status, '')) NOT IN
          ('تم التسليم', 'DELIVERED', 'ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      )::integer AS open_orders,
      count(*) FILTER (
        WHERE trim(coalesce(status, '')) NOT IN
          ('تم التسليم', 'DELIVERED', 'ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
          AND profit IS NULL
      )::integer AS open_missing_profit_orders,
      coalesce(sum(total) FILTER (
        WHERE trim(coalesce(status, '')) NOT IN
          ('تم التسليم', 'DELIVERED', 'ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      ), 0)::numeric AS open_order_value,
      count(*) FILTER (
        WHERE trim(coalesce(status, '')) IN ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      )::integer AS cancelled_orders,
      coalesce(sum(total) FILTER (
        WHERE trim(coalesce(status, '')) IN ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      ), 0)::numeric AS cancelled_order_value
    FROM scoped_orders
  ),
  daily AS (
    SELECT coalesce(jsonb_agg(to_jsonb(d) ORDER BY d.day), '[]'::jsonb) AS rows
    FROM (
      SELECT
        (created_at AT TIME ZONE 'Africa/Cairo')::date::text AS day,
        count(*) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
        )::integer AS delivered_orders,
        coalesce(sum(total) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
        ), 0)::numeric AS delivered_sales,
        coalesce(sum(profit) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
        ), 0)::numeric AS product_gross_margin,
        count(*) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
            AND profit IS NULL
        )::integer AS missing_profit_orders,
        count(*) FILTER (
          WHERE trim(coalesce(status, '')) NOT IN
            ('تم التسليم', 'DELIVERED', 'ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
            AND profit IS NULL
        )::integer AS open_missing_profit_orders,
        count(*) FILTER (
          WHERE trim(coalesce(status, '')) NOT IN
            ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
        )::integer AS requested_orders
      FROM scoped_orders
      WHERE trim(coalesce(status, '')) NOT IN ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      GROUP BY 1
    ) d
  ),
  product_lines AS (
    SELECT
      coalesce(
        nullif(item->>'product_id', ''),
        nullif(item->>'product_code', ''),
        nullif(item->>'code', ''),
        nullif(item->>'product_name', ''),
        nullif(item->>'name', ''),
        'unknown'
      ) AS product_key,
      coalesce(
        nullif(item->>'product_name', ''),
        nullif(item->>'name', ''),
        'منتج غير معروف'
      ) AS product_name,
      greatest(0, coalesce(nullif(item->>'quantity', '')::numeric, 0)) AS quantity,
      coalesce(
        nullif(item->>'price', '')::numeric,
        nullif(item->>'unit_price', '')::numeric,
        0
      ) AS unit_price,
      o.id AS order_id,
      trim(coalesce(o.status, '')) AS order_status
    FROM scoped_orders o
    CROSS JOIN LATERAL jsonb_array_elements(
      CASE WHEN jsonb_typeof(o.items) = 'array' THEN o.items ELSE '[]'::jsonb END
    ) AS item
    WHERE trim(coalesce(o.status, '')) NOT IN
      ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
  ),
  products AS (
    SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.requested_units DESC, p.requested_orders DESC), '[]'::jsonb) AS rows
    FROM (
      SELECT
        product_key,
        product_name,
        sum(quantity)::integer AS requested_units,
        coalesce(sum(quantity) FILTER (
          WHERE order_status IN ('تم التسليم', 'DELIVERED')
        ), 0)::integer AS delivered_units,
        coalesce(sum(quantity) FILTER (
          WHERE order_status NOT IN ('تم التسليم', 'DELIVERED')
        ), 0)::integer AS open_units,
        count(DISTINCT order_id)::integer AS requested_orders,
        coalesce(sum(unit_price * quantity) FILTER (
          WHERE order_status IN ('تم التسليم', 'DELIVERED')
        ), 0)::numeric AS delivered_item_sales
      FROM product_lines
      GROUP BY product_key, product_name
      ORDER BY sum(quantity) DESC, count(DISTINCT order_id) DESC
      LIMIT 10
    ) p
  ),
  governorates AS (
    SELECT coalesce(jsonb_agg(to_jsonb(g) ORDER BY g.requested_orders DESC, g.requested_value DESC), '[]'::jsonb) AS rows
    FROM (
      SELECT
        coalesce(nullif(trim(governorate), ''), 'غير محدد') AS governorate,
        count(*)::integer AS requested_orders,
        count(*) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
        )::integer AS delivered_orders,
        coalesce(sum(total), 0)::numeric AS requested_value,
        coalesce(sum(total) FILTER (
          WHERE trim(coalesce(status, '')) IN ('تم التسليم', 'DELIVERED')
        ), 0)::numeric AS delivered_value
      FROM scoped_orders
      WHERE trim(coalesce(status, '')) NOT IN
        ('ملغي', 'ملغى', 'CANCELLED', 'CANCELED')
      GROUP BY 1
      ORDER BY count(*) DESC, coalesce(sum(total), 0) DESC
      LIMIT 10
    ) g
  ),
  prime_rows AS (
    SELECT
      ps.id,
      ps.status,
      ps.active,
      ps.started_at,
      ps.expires_at,
      ps.free_shipping_limit,
      ps.discount_percent,
      ps.price AS membership_price,
      ps.order_id,
      ps.actual_free_shipping_cost_total,
      membership_order.order_number,
      CASE
        WHEN ps.order_id IS NOT NULL
         AND trim(coalesce(membership_order.status, '')) IN ('تم التسليم', 'DELIVERED')
        THEN coalesce(ps.price, 0)
        ELSE NULL
      END AS membership_revenue,
      coalesce(usage.free_shipping_used, 0)::integer AS free_shipping_used,
      greatest(0, coalesce(ps.free_shipping_limit, 0) - coalesce(usage.free_shipping_used, 0))::integer
        AS free_shipping_remaining,
      coalesce(usage.free_shipping_completed, 0)::integer AS free_shipping_completed,
      coalesce(usage.prime_discount_total, 0)::numeric AS prime_discount_total,
      coalesce(usage.prime_discount_pending, 0)::numeric AS prime_discount_pending,
      coalesce(usage.free_shipping_completed, 0)::integer AS free_shipping_orders,
      (
        ps.order_id IS NOT NULL
        AND trim(coalesce(membership_order.status, '')) IN ('تم التسليم', 'DELIVERED')
        AND (
          coalesce(usage.free_shipping_used, 0) = 0
          OR ps.actual_free_shipping_cost_total IS NOT NULL
        )
      ) AS financial_complete,
      CASE
        WHEN ps.order_id IS NULL
          OR trim(coalesce(membership_order.status, '')) NOT IN ('تم التسليم', 'DELIVERED')
          THEN NULL
        WHEN coalesce(usage.free_shipping_used, 0) > 0
          AND ps.actual_free_shipping_cost_total IS NULL
          THEN NULL
        ELSE round(
          coalesce(ps.price, 0)
          - coalesce(usage.prime_discount_total, 0)
          - coalesce(ps.actual_free_shipping_cost_total, 0),
          2
        )
      END AS prime_profit
    FROM public.prime_subscriptions ps
    LEFT JOIN public.orders membership_order ON membership_order.id = ps.order_id
    LEFT JOIN LATERAL (
      SELECT
        count(*) FILTER (
          WHERE coalesce(o.prime, false) IS TRUE
            AND coalesce(o.prime_free_shipping, false) IS TRUE
            AND trim(coalesce(o.status, '')) IN ('تم الشحن', 'تم التسليم', 'DELIVERED')
        )::integer AS free_shipping_used,
        count(*) FILTER (
          WHERE coalesce(o.prime, false) IS TRUE
            AND coalesce(o.prime_free_shipping, false) IS TRUE
            AND trim(coalesce(o.status, '')) IN ('تم التسليم', 'DELIVERED')
        )::integer AS free_shipping_completed,
        coalesce(sum(coalesce(o.prime_discount, 0)) FILTER (
          WHERE coalesce(o.prime, false) IS TRUE
            AND trim(coalesce(o.status, '')) IN ('تم التسليم', 'DELIVERED')
        ), 0)::numeric AS prime_discount_total,
        coalesce(sum(coalesce(o.prime_discount, 0)) FILTER (
          WHERE coalesce(o.prime, false) IS TRUE
            AND trim(coalesce(o.status, '')) NOT IN
              ('تم التسليم', 'DELIVERED', 'ملغي', 'ملغى', 'CANCELLED', 'CANCELED', 'فشل الدفع', 'فشل إنشاء الدفع', 'FAILED')
        ), 0)::numeric AS prime_discount_pending
      FROM public.orders o
      WHERE ps.user_id IS NOT NULL
        AND (o.user_id = ps.user_id OR o.customer_user_id = ps.user_id)
        AND o.created_at >= coalesce(ps.started_at, ps.created_at)
        AND (ps.expires_at IS NULL OR o.created_at <= ps.expires_at)
        AND NOT EXISTS (
          SELECT 1
          FROM public.prime_subscriptions newer
          WHERE newer.user_id = ps.user_id
            AND newer.id <> ps.id
            AND coalesce(newer.status, '') NOT IN ('failed', 'cancelled', 'inactive')
            AND coalesce(newer.started_at, newer.created_at) <= o.created_at
            AND (newer.expires_at IS NULL OR newer.expires_at >= o.created_at)
            AND (
              coalesce(newer.started_at, newer.created_at) > coalesce(ps.started_at, ps.created_at)
              OR (
                coalesce(newer.started_at, newer.created_at) = coalesce(ps.started_at, ps.created_at)
                AND newer.created_at > ps.created_at
              )
            )
        )
    ) usage ON true
  ),
  prime AS (
    SELECT coalesce(jsonb_agg(to_jsonb(p) ORDER BY p.started_at DESC NULLS LAST), '[]'::jsonb) AS rows
    FROM prime_rows p
  )
  SELECT jsonb_build_object(
    'period_days', v_days,
    'from', v_from,
    'to', now(),
    'summary', (SELECT to_jsonb(s) FROM summary s),
    'daily', (SELECT rows FROM daily),
    'products', (SELECT rows FROM products),
    'governorates', (SELECT rows FROM governorates),
    'prime', (SELECT rows FROM prime)
  ) INTO v_result;

  RETURN v_result;
END;
$function$;

REVOKE ALL ON FUNCTION public.admin_get_profit_dashboard(integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION public.admin_get_profit_dashboard(integer) FROM anon;
GRANT EXECUTE ON FUNCTION public.admin_get_profit_dashboard(integer) TO authenticated;

COMMIT;
