-- Read-only dashboard customer directory derived from the canonical orders table.
-- The app currently calls GET /rest/v1/customers, but no customers table exists.
-- security_invoker keeps the existing orders RLS policy (orders.view) in force.
CREATE OR REPLACE VIEW public.customers
WITH (security_invoker = true)
AS
SELECT
    'cust_' || pg_catalog.md5(pg_catalog.btrim(o.phone)) AS id,
    COALESCE(
        (
            pg_catalog.array_agg(
                NULLIF(pg_catalog.btrim(o.customer_name), '')
                ORDER BY o.created_at DESC, o.id DESC
            ) FILTER (WHERE NULLIF(pg_catalog.btrim(o.customer_name), '') IS NOT NULL)
        )[1],
        'عميل غير معروف'
    ) AS name,
    pg_catalog.btrim(o.phone) AS phone,
    NULL::text AS email,
    (
        pg_catalog.array_agg(
            NULLIF(pg_catalog.btrim(o.address), '')
            ORDER BY o.created_at DESC, o.id DESC
        ) FILTER (WHERE NULLIF(pg_catalog.btrim(o.address), '') IS NOT NULL)
    )[1] AS address,
    (
        pg_catalog.array_agg(
            NULLIF(pg_catalog.btrim(o.governorate), '')
            ORDER BY o.created_at DESC, o.id DESC
        ) FILTER (WHERE NULLIF(pg_catalog.btrim(o.governorate), '') IS NOT NULL)
    )[1] AS governorate,
    pg_catalog.count(*)::integer AS total_orders,
    COALESCE(pg_catalog.sum(o.total), 0)::numeric AS total_spend,
    pg_catalog.min(o.created_at) AS first_order_date,
    pg_catalog.max(o.created_at) AS last_order_date,
    pg_catalog.bool_or(COALESCE(o.prime, false)) AS is_prime_member
FROM public.orders AS o
WHERE o.phone IS NOT NULL
  AND pg_catalog.btrim(o.phone) <> ''
GROUP BY pg_catalog.btrim(o.phone);

GRANT SELECT ON TABLE public.customers TO authenticated;
