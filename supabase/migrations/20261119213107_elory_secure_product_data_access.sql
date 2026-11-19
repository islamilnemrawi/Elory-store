-- Protect internal product fields without removing the public catalog or staff workflows.
-- Public storefront reads continue through catalog_products; staff reads use an
-- authorization-checked RPC with per-field permission filtering.

BEGIN;

DO $preflight$
DECLARE
  v_missing text[];
BEGIN
  IF to_regclass('public.products') IS NULL
     OR to_regclass('public.catalog_products') IS NULL
     OR to_regclass('public.coupons') IS NULL
     OR to_regclass('public.owner_data_reset_settings') IS NULL
     OR to_regclass('public.owner_data_reset_audit') IS NULL THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: an expected table or view is missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = 'catalog_products'
       AND c.reloptions @> ARRAY['security_invoker=true']
  ) THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: catalog_products must remain SECURITY INVOKER';
  END IF;

  SELECT array_agg(required.column_name)
    INTO v_missing
    FROM (VALUES
      ('id'), ('name'), ('description'), ('image'), ('category'), ('price'),
      ('old_price'), ('wholesale_price'), ('code'), ('stock'), ('discount'),
      ('featured'), ('active'), ('created_at'), ('colors'), ('sizes'),
      ('variants'), ('sku'), ('weight'), ('gallery'), ('color_options')
    ) AS required(column_name)
   WHERE NOT EXISTS (
     SELECT 1
       FROM information_schema.columns c
      WHERE c.table_schema = 'public'
        AND c.table_name = 'products'
        AND c.column_name = required.column_name
   );

  IF v_missing IS NOT NULL THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: products is missing columns %', v_missing;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'products'
       AND policyname = 'pinky_public_active_products'
       AND cmd = 'SELECT'
  ) OR NOT EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'products'
       AND policyname = 'staff_products_select_grant'
       AND cmd = 'SELECT'
  ) THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: existing public/staff product read policies were not found';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'coupons'
       AND policyname = 'Public can validate coupon by code'
       AND cmd = 'SELECT'
  ) THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: expected public coupon SELECT policy was not found';
  END IF;

  IF to_regprocedure('public.has_staff_permission(text)') IS NULL THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: staff permission function is missing';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema='public' AND table_name='owner_data_reset_settings' AND column_name='owner_id'
  ) OR NOT EXISTS (
    SELECT 1 FROM information_schema.columns
     WHERE table_schema='public' AND table_name='owner_data_reset_audit' AND column_name='owner_id'
  ) THEN
    RAISE EXCEPTION 'Elory product access hardening stopped: owner_id index columns are missing';
  END IF;
END;
$preflight$;

-- The public view exposes only catalog-safe fields. Revoke table-wide SELECT,
-- then grant only the columns required by that SECURITY INVOKER view.
REVOKE SELECT ON TABLE public.products FROM anon, authenticated;
REVOKE SELECT (wholesale_price, code, stock, sku, weight)
  ON TABLE public.products FROM anon, authenticated;

GRANT SELECT (
  id, name, description, image, category, price, old_price, discount,
  featured, active, created_at, colors, color_options, sizes, variants,
  gallery
) ON TABLE public.products TO anon, authenticated;

-- Keep active products visible publicly and allow staff to see inactive products.
DROP POLICY IF EXISTS "Staff product select permission" ON public.products;
DROP POLICY IF EXISTS "pinky_public_active_products" ON public.products;
DROP POLICY IF EXISTS "staff_products_select_grant" ON public.products;

CREATE POLICY "pinky_public_active_products"
  ON public.products
  AS PERMISSIVE
  FOR SELECT
  TO anon
  USING (COALESCE(active, true) IS TRUE);

CREATE POLICY "staff_products_select_grant"
  ON public.products
  AS PERMISSIVE
  FOR SELECT
  TO authenticated
  USING (
    COALESCE(active, true) IS TRUE
    OR (SELECT public.has_staff_permission('products.view'::text))
  );

-- Coupons are validated through the existing server-side RPC. Do not expose the
-- coupon table itself to anonymous visitors; staff keeps the existing RLS path.
DROP POLICY "Public can validate coupon by code" ON public.coupons;
REVOKE SELECT ON TABLE public.coupons FROM anon;

-- Add indexes for the two owner_id foreign keys without touching existing rows.
CREATE INDEX IF NOT EXISTS idx_owner_data_reset_settings_owner_id
  ON public.owner_data_reset_settings (owner_id);
CREATE INDEX IF NOT EXISTS idx_owner_data_reset_audit_owner_id
  ON public.owner_data_reset_audit (owner_id);

-- Privileged product reads stay behind a private, permission-checked implementation.
CREATE SCHEMA IF NOT EXISTS private;

CREATE OR REPLACE FUNCTION private.elory_admin_list_products_impl(
  p_limit integer,
  p_offset integer
)
RETURNS SETOF jsonb
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO pg_catalog
AS $function$
DECLARE
  v_limit integer := GREATEST(1, LEAST(COALESCE(p_limit, 500), 1000));
  v_offset integer := GREATEST(0, LEAST(COALESCE(p_offset, 0), 100000000));
  v_hidden_fields text[] := ARRAY[]::text[];
BEGIN
  IF auth.uid() IS NULL THEN
    RAISE EXCEPTION 'يجب تسجيل الدخول لعرض بيانات المنتجات'
      USING ERRCODE = '42501';
  END IF;

  IF NOT public.has_staff_permission('products.view'::text) THEN
    RAISE EXCEPTION 'ليس لديك صلاحية عرض المنتجات'
      USING ERRCODE = '42501';
  END IF;

  IF NOT public.has_staff_permission('products.wholesale_prices'::text) THEN
    v_hidden_fields := v_hidden_fields || ARRAY['wholesale_price'];
  END IF;

  IF NOT public.has_staff_permission('products.internal_codes'::text) THEN
    v_hidden_fields := v_hidden_fields || ARRAY['code', 'sku'];
  END IF;

  RETURN QUERY
    SELECT to_jsonb(p) - v_hidden_fields
      FROM public.products AS p
     ORDER BY p.id ASC
     LIMIT v_limit
    OFFSET v_offset;
END;
$function$;

REVOKE ALL ON FUNCTION private.elory_admin_list_products_impl(integer, integer)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT USAGE ON SCHEMA private TO authenticated;
GRANT EXECUTE ON FUNCTION private.elory_admin_list_products_impl(integer, integer)
  TO authenticated;

CREATE OR REPLACE FUNCTION public.admin_list_products(
  p_limit integer DEFAULT 500,
  p_offset integer DEFAULT 0
)
RETURNS SETOF jsonb
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path TO pg_catalog
AS $function$
  SELECT *
    FROM private.elory_admin_list_products_impl($1, $2);
$function$;

REVOKE ALL ON FUNCTION public.admin_list_products(integer, integer)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.admin_list_products(integer, integer)
  TO authenticated;

NOTIFY pgrst, 'reload schema';

COMMIT;
