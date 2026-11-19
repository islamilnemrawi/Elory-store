-- Run after product_access_hardening_fixture.sql and the migration.
INSERT INTO auth.users(id) VALUES ('11111111-1111-4111-8111-111111111111');
INSERT INTO public.products(
  id, name, description, category, price, wholesale_price, code, stock,
  discount, featured, active, created_at, colors, sizes, variants, sku, weight,
  gallery, color_options
) VALUES (
  '22222222-2222-4222-8222-222222222222',
  'Test product', 'Fixture only', 'Test', 100, 45, 'ELORY-PRIVATE-1', 5,
  0, false, true, now(), '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, 'SKU-PRIVATE-1',
  0.2, '[]'::jsonb, '[]'::jsonb
);
INSERT INTO public.products(
  id, name, category, price, wholesale_price, code, active
) VALUES (
  '33333333-3333-4333-8333-333333333333',
  'Inactive fixture', 'Test', 200, 90, 'ELORY-INACTIVE-1', false
);
INSERT INTO public.coupons(id, code, active)
VALUES ('44444444-4444-4444-8444-444444444444', 'FIXTUREONLY', true);

-- Anonymous visitors can still read the safe public catalog, but cannot read
-- internal columns or enumerate the coupons table.
SET ROLE anon;
DO $anon$
BEGIN
  IF has_table_privilege('anon', 'public.products', 'SELECT') THEN
    RAISE EXCEPTION 'anon unexpectedly has table-wide products SELECT';
  END IF;
  IF NOT has_column_privilege('anon', 'public.products', 'name', 'SELECT') THEN
    RAISE EXCEPTION 'anon lost the public product columns';
  END IF;
  IF has_column_privilege('anon', 'public.products', 'wholesale_price', 'SELECT')
     OR has_column_privilege('anon', 'public.products', 'code', 'SELECT')
     OR has_column_privilege('anon', 'public.products', 'sku', 'SELECT')
     OR has_column_privilege('anon', 'public.products', 'stock', 'SELECT')
     OR has_column_privilege('anon', 'public.products', 'weight', 'SELECT') THEN
    RAISE EXCEPTION 'anon can still read internal product fields';
  END IF;
  IF has_table_privilege('anon', 'public.coupons', 'SELECT') THEN
    RAISE EXCEPTION 'anon can still enumerate the coupons table';
  END IF;
  IF has_function_privilege('anon', 'public.admin_list_products(integer,integer)', 'EXECUTE') THEN
    RAISE EXCEPTION 'anon can execute the staff product RPC';
  END IF;
END;
$anon$;
DO $anon_catalog$
DECLARE v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.catalog_products;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'Public catalog should still expose exactly the active fixture product; found %', v_count;
  END IF;
END;
$anon_catalog$;

-- Match the exact public product columns requested by the live storefront.
-- This must keep working after table-wide SELECT is revoked and replaced by
-- safe column-level grants. Product detail reads that request stock must fail
-- closed and use catalog_products as their existing fallback.
DO $anon_storefront_query$
DECLARE v_count integer;
BEGIN
  SELECT count(*) INTO v_count
    FROM (
      SELECT id, name, description, image, category, price, old_price,
             discount, featured, active, colors, color_options, sizes,
             variants, created_at
        FROM public.products
       WHERE active IS TRUE
    ) AS storefront_rows;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'The storefront public products query should return the active fixture row; found %', v_count;
  END IF;

  BEGIN
    PERFORM stock FROM public.products WHERE active IS TRUE;
    RAISE EXCEPTION 'Anonymous product-detail query unexpectedly read private stock';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;

  SELECT count(*) INTO v_count FROM public.catalog_products;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'The catalog_products fallback should remain available; found %', v_count;
  END IF;
END;
$anon_storefront_query$;
RESET ROLE;

-- A signed-in customer retains active public catalog access, but no private fields.
SET ROLE authenticated;
SELECT set_config('request.jwt.claim.sub', '', false);
SELECT set_config('test.permissions', '', false);
DO $customer$
DECLARE v_count integer;
BEGIN
  IF has_column_privilege('authenticated', 'public.products', 'wholesale_price', 'SELECT')
     OR has_column_privilege('authenticated', 'public.products', 'code', 'SELECT')
     OR has_column_privilege('authenticated', 'public.products', 'sku', 'SELECT') THEN
    RAISE EXCEPTION 'authenticated can still read internal product columns directly';
  END IF;
  SELECT count(*) INTO v_count FROM public.catalog_products;
  IF v_count <> 1 THEN
    RAISE EXCEPTION 'Authenticated customers should retain active catalog access; found %', v_count;
  END IF;
  BEGIN
    PERFORM * FROM public.admin_list_products(100, 0);
    RAISE EXCEPTION 'Unauthenticated caller unexpectedly read admin products';
  EXCEPTION WHEN insufficient_privilege THEN
    NULL;
  END;
END;
$customer$;

-- A permitted staff member can read all products through the RPC, while the
-- server strips fields for which their account lacks explicit permission.
SELECT set_config('request.jwt.claim.sub', '11111111-1111-4111-8111-111111111111', false);
SELECT set_config('test.permissions', 'products.view', false);
DO $staff_limited$
DECLARE v_row jsonb; v_count integer;
BEGIN
  SELECT count(*) INTO v_count FROM public.admin_list_products(100, 0);
  IF v_count <> 2 THEN
    RAISE EXCEPTION 'products.view staff should receive active and inactive products; found %', v_count;
  END IF;
  SELECT value INTO v_row FROM public.admin_list_products(100, 0) AS value
   WHERE value->>'id' = '22222222-2222-4222-8222-222222222222';
  IF v_row ? 'wholesale_price' OR v_row ? 'code' OR v_row ? 'sku' THEN
    RAISE EXCEPTION 'RPC leaked fields without their explicit staff permissions';
  END IF;
END;
$staff_limited$;

-- Explicitly authorized staff retain the protected fields needed by the product UI.
SELECT set_config('test.permissions', 'products.view,products.wholesale_prices,products.internal_codes', false);
DO $staff_full$
DECLARE v_row jsonb;
BEGIN
  SELECT value INTO v_row FROM public.admin_list_products(100, 0) AS value
   WHERE value->>'id' = '22222222-2222-4222-8222-222222222222';
  IF v_row->>'wholesale_price' <> '45'
     OR v_row->>'code' <> 'ELORY-PRIVATE-1'
     OR v_row->>'sku' <> 'SKU-PRIVATE-1' THEN
    RAISE EXCEPTION 'Authorized staff lost their wholesale/internal-code fields';
  END IF;
END;
$staff_full$;
RESET ROLE;

DO $indexes$
BEGIN
  IF to_regclass('public.idx_owner_data_reset_settings_owner_id') IS NULL
     OR to_regclass('public.idx_owner_data_reset_audit_owner_id') IS NULL THEN
    RAISE EXCEPTION 'Expected owner reset FK indexes are missing';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'products'
       AND policyname = 'Staff product select permission'
  ) THEN
    RAISE EXCEPTION 'Obsolete restrictive product SELECT policy remains';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'coupons'
       AND policyname = 'Public can validate coupon by code'
  ) THEN
    RAISE EXCEPTION 'Public coupon table SELECT policy remains';
  END IF;
  IF NOT has_function_privilege('authenticated', 'public.admin_list_products(integer,integer)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.admin_list_products(integer,integer)', 'EXECUTE') THEN
    RAISE EXCEPTION 'admin_list_products RPC grants are incorrect';
  END IF;
END;
$indexes$;
