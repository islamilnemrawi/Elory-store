-- Run after security_hardening_fixture.sql and the migration on disposable PostgreSQL 17.

DO $metadata$
DECLARE
  v_api_names text[] := ARRAY[
    'admin_apply_shipping_governorate_price','admin_delete_order','admin_delete_shipping_center',
    'admin_get_my_staff_profile','admin_grant_prime_by_email','admin_list_orders',
    'admin_list_prime_subscriptions','admin_list_shipping','admin_list_staff',
    'admin_save_shipping_center','admin_save_shipping_governorate','admin_set_prime_subscription_active',
    'admin_set_staff_active','admin_update_order_status','admin_upsert_staff_by_email',
    'elora_admin_allowed','get_customer_orders','get_my_prime_status','has_staff_permission',
    'is_elora_staff','redeem_coupon','register_dashboard_push_device'
  ];
BEGIN
  IF EXISTS (
    SELECT 1
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.proname = ANY (v_api_names)
       AND p.prosecdef IS TRUE
  ) THEN
    RAISE EXCEPTION 'A public Elory RPC still runs as SECURITY DEFINER';
  END IF;

  IF EXISTS (
    SELECT 1
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'private'
       AND p.proname = ANY (v_api_names)
       AND p.prosecdef IS NOT TRUE
  ) THEN
    RAISE EXCEPTION 'A private Elory implementation lost SECURITY DEFINER';
  END IF;

  IF EXISTS (
    SELECT 1
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.proname = ANY (v_api_names)
       AND EXISTS (
         SELECT 1
           FROM aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) AS function_acl
          WHERE function_acl.grantee = 0
            AND function_acl.privilege_type = 'EXECUTE'
       )
  ) THEN
    RAISE EXCEPTION 'A public Elory RPC is executable by PUBLIC';
  END IF;

  IF NOT has_function_privilege('authenticated', 'public.admin_delete_order(uuid)', 'EXECUTE')
     OR has_function_privilege('anon', 'public.admin_delete_order(uuid)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Admin RPC grants were not narrowed to authenticated users';
  END IF;

  IF NOT has_function_privilege('anon', 'public.get_customer_orders(text,text)', 'EXECUTE')
     OR NOT has_function_privilege('authenticated', 'public.get_customer_orders(text,text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Guest/customer order-tracking RPC access was not preserved';
  END IF;

  IF NOT has_function_privilege('anon', 'public.redeem_coupon(uuid,uuid,text)', 'EXECUTE')
     OR NOT has_function_privilege('service_role', 'public.redeem_coupon(uuid,uuid,text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'Coupon redemption grants were not preserved';
  END IF;

  IF NOT has_function_privilege('authenticated', 'private.has_staff_permission(text)', 'EXECUTE')
     OR has_function_privilege('anon', 'private.has_staff_permission(text)', 'EXECUTE') THEN
    RAISE EXCEPTION 'RLS helper privileges are incorrect';
  END IF;

  IF (SELECT prosecdef FROM pg_proc WHERE oid = 'public.validate_coupon(text,numeric)'::regprocedure) IS TRUE THEN
    RAISE EXCEPTION 'validate_coupon is still SECURITY DEFINER';
  END IF;

  IF NOT has_schema_privilege('authenticated', 'private', 'USAGE')
     OR NOT has_schema_privilege('anon', 'private', 'USAGE') THEN
    RAISE EXCEPTION 'RPC roles cannot resolve private implementations';
  END IF;
END;
$metadata$;

-- Verify existing public tables no longer grant out-of-band privileges.
DO $table_privileges$
DECLARE
  r record;
BEGIN
  FOR r IN
    SELECT c.oid, c.relname
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relkind IN ('r', 'p')
  LOOP
    IF has_table_privilege('anon', r.oid, 'TRUNCATE')
       OR has_table_privilege('authenticated', r.oid, 'TRUNCATE')
       OR has_table_privilege('anon', r.oid, 'REFERENCES')
       OR has_table_privilege('authenticated', r.oid, 'REFERENCES')
       OR has_table_privilege('anon', r.oid, 'TRIGGER')
       OR has_table_privilege('authenticated', r.oid, 'TRIGGER')
       OR has_table_privilege('anon', r.oid, 'MAINTAIN')
       OR has_table_privilege('authenticated', r.oid, 'MAINTAIN') THEN
      RAISE EXCEPTION 'Unexpected table-level privilege remains on public.%', r.relname;
    END IF;
  END LOOP;
END;
$table_privileges$;

-- Verify future postgres-owned public tables/functions inherit the tightened
-- default privileges rather than silently re-opening the API surface.
CREATE TABLE public.security_fixture_future_probe(id integer);
CREATE FUNCTION public.security_fixture_future_fn()
RETURNS integer LANGUAGE sql AS 'SELECT 1';

CREATE TABLE private.security_fixture_future_probe(id integer);
CREATE FUNCTION private.security_fixture_future_fn()
RETURNS integer LANGUAGE sql AS 'SELECT 1';

DO $defaults$
BEGIN
  IF has_table_privilege('anon', 'public.security_fixture_future_probe', 'TRUNCATE')
     OR has_table_privilege('authenticated', 'public.security_fixture_future_probe', 'TRUNCATE')
     OR has_table_privilege('anon', 'public.security_fixture_future_probe', 'REFERENCES')
     OR has_table_privilege('authenticated', 'public.security_fixture_future_probe', 'REFERENCES')
     OR has_table_privilege('anon', 'public.security_fixture_future_probe', 'TRIGGER')
     OR has_table_privilege('authenticated', 'public.security_fixture_future_probe', 'TRIGGER')
     OR has_table_privilege('anon', 'public.security_fixture_future_probe', 'MAINTAIN')
     OR has_table_privilege('authenticated', 'public.security_fixture_future_probe', 'MAINTAIN') THEN
    RAISE EXCEPTION 'Unsafe table default privileges remain for postgres-owned public tables';
  END IF;

  IF has_function_privilege('anon', 'public.security_fixture_future_fn()', 'EXECUTE')
     OR has_function_privilege('authenticated', 'public.security_fixture_future_fn()', 'EXECUTE')
     OR EXISTS (
       SELECT 1
         FROM pg_proc p
         CROSS JOIN LATERAL aclexplode(COALESCE(p.proacl, acldefault('f', p.proowner))) AS function_acl
        WHERE p.oid = 'public.security_fixture_future_fn()'::regprocedure
          AND function_acl.grantee = 0
          AND function_acl.privilege_type = 'EXECUTE'
     ) THEN
    RAISE EXCEPTION 'Unsafe function default EXECUTE remains for postgres-owned functions';
  END IF;

  IF has_table_privilege('anon', 'private.security_fixture_future_probe', 'SELECT')
     OR has_table_privilege('authenticated', 'private.security_fixture_future_probe', 'SELECT')
     OR has_table_privilege('anon', 'private.security_fixture_future_probe', 'INSERT')
     OR has_table_privilege('authenticated', 'private.security_fixture_future_probe', 'INSERT')
     OR has_table_privilege('anon', 'private.security_fixture_future_probe', 'UPDATE')
     OR has_table_privilege('authenticated', 'private.security_fixture_future_probe', 'UPDATE')
     OR has_table_privilege('anon', 'private.security_fixture_future_probe', 'DELETE')
     OR has_table_privilege('authenticated', 'private.security_fixture_future_probe', 'DELETE')
     OR has_function_privilege('anon', 'private.security_fixture_future_fn()', 'EXECUTE')
     OR has_function_privilege('authenticated', 'private.security_fixture_future_fn()', 'EXECUTE')
     OR has_function_privilege('public', 'private.security_fixture_future_fn()', 'EXECUTE') THEN
    RAISE EXCEPTION 'Private-schema default privileges exposed a future object to API roles';
  END IF;

  IF has_schema_privilege('anon', 'private', 'CREATE')
     OR has_schema_privilege('authenticated', 'private', 'CREATE') THEN
    RAISE EXCEPTION 'API roles can create objects in the private schema';
  END IF;
END;
$defaults$;

-- The RLS policy references the original has_staff_permission function OID.
-- After that function moves to private, the dependency and its access must work.
SET ROLE authenticated;
DO $rls_dependency$
DECLARE
  v_rows integer;
BEGIN
  SELECT count(*) INTO v_rows FROM public.security_fixture_policy_probe;
  IF v_rows <> 0 THEN
    RAISE EXCEPTION 'Moved has_staff_permission policy did not deny an unverified user';
  END IF;

  BEGIN
    PERFORM public.admin_delete_order('10000000-0000-4000-8000-000000000010');
    RAISE EXCEPTION 'Admin RPC unexpectedly allowed an unverified authenticated user';
  EXCEPTION
    WHEN OTHERS THEN
      IF SQLERRM <> 'fixture staff access denied' THEN
        RAISE;
      END IF;
  END;
END;
$rls_dependency$;
RESET ROLE;

-- Exercise every dashboard/admin RPC wrapper through the original PostgREST
-- function names while authenticated. The synthetic staff gate accepts a
-- non-null auth.uid(), so failures here indicate wrapper/grant/schema issues.
SET ROLE authenticated;
DO $dashboard_rpc_compatibility$
DECLARE
  v_ok boolean;
  v_count integer;
  v_json jsonb;
BEGIN
  PERFORM set_config(
    'request.jwt.claim.sub',
    '10000000-0000-4000-8000-000000000099',
    false
  );

  IF public.has_staff_permission('fixture.view') IS NOT TRUE
     OR public.elora_admin_allowed() IS NOT TRUE
     OR public.is_elora_staff() IS NOT TRUE THEN
    RAISE EXCEPTION 'Authenticated staff helper RPCs did not execute';
  END IF;

  IF public.admin_get_my_staff_profile() IS NULL THEN
    RAISE EXCEPTION 'Staff profile RPC did not execute for authenticated user';
  END IF;

  v_json := public.admin_apply_shipping_governorate_price('Test Governorate', 25);
  PERFORM public.admin_delete_order('10000000-0000-4000-8000-000000000010');
  PERFORM public.admin_delete_shipping_center('test-center');
  PERFORM public.admin_save_shipping_center('test-center', 'Test Governorate', 'Test Center', 25, true);
  PERFORM public.admin_save_shipping_governorate('Test Governorate', 25, true, true);
  PERFORM public.admin_set_prime_subscription_active('10000000-0000-4000-8000-000000000011', true);
  PERFORM public.admin_set_staff_active('10000000-0000-4000-8000-000000000012', true);
  PERFORM public.admin_update_order_status('10000000-0000-4000-8000-000000000013', 'جاري التجهيز');
  PERFORM public.admin_upsert_staff_by_email('fixture@example.test', 'Fixture Staff', 'staff', '{}'::jsonb, true);

  SELECT success INTO v_ok
    FROM public.admin_grant_prime_by_email('fixture@example.test', 30);
  IF v_ok IS NOT TRUE THEN
    RAISE EXCEPTION 'Prime grant RPC returned an unsuccessful fixture result';
  END IF;

  SELECT count(*) INTO v_count FROM public.admin_list_orders(10);
  SELECT count(*) INTO v_count FROM public.admin_list_prime_subscriptions();
  SELECT count(*) INTO v_count FROM public.admin_list_staff();
  v_json := public.admin_list_shipping();

  IF v_json IS NULL THEN
    RAISE EXCEPTION 'Shipping list RPC returned NULL';
  END IF;

  IF (public.get_my_prime_status()->>'active')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'Prime status RPC did not execute for authenticated user';
  END IF;

  v_json := public.register_dashboard_push_device('test-device-token-0123456789', 'android');
  IF (v_json->>'ok')::boolean IS NOT TRUE THEN
    RAISE EXCEPTION 'Dashboard push-device registration wrapper failed';
  END IF;
END;
$dashboard_rpc_compatibility$;
RESET ROLE;

-- Public guest endpoints remain usable only with a valid auth identity or
-- access token; the anonymous no-token path must not reveal order rows.
SET ROLE anon;
DO $guest_access$
DECLARE
  v_rows integer;
BEGIN
  -- Simulate a fresh anonymous PostgREST request, not the previous authenticated
  -- fixture session on this same psql connection.
  PERFORM set_config('request.jwt.claim.sub', '', false);
  PERFORM set_config('request.jwt.claim.role', 'anon', false);

  IF auth.role() <> 'anon' OR auth.uid() IS NOT NULL THEN
    RAISE EXCEPTION 'Anonymous fixture context incorrect: role=%, uid=%', auth.role(), auth.uid();
  END IF;

  SELECT count(*) INTO v_rows FROM public.get_customer_orders();
  IF v_rows <> 0 THEN
    RAISE EXCEPTION 'Anonymous order tracking returned rows without proof';
  END IF;

  IF public.redeem_coupon(
    '10000000-0000-4000-8000-000000000001',
    '10000000-0000-4000-8000-000000000010',
    NULL
  ) IS TRUE THEN
    RAISE EXCEPTION 'Anonymous coupon redemption succeeded without proof';
  END IF;
END;
$guest_access$;
RESET ROLE;

-- SECURITY INVOKER coupon validation is subject to the active-only RLS policy.
SET ROLE anon;
DO $coupon_rls$
DECLARE
  v_active_count integer;
  v_inactive_valid_count integer;
BEGIN
  SELECT count(*) INTO v_active_count
    FROM public.validate_coupon('ACTIVE10', 100)
   WHERE valid IS TRUE;

  SELECT count(*) INTO v_inactive_valid_count
    FROM public.validate_coupon('INACTIVE10', 100)
   WHERE valid IS TRUE;

  IF v_active_count <> 1 OR v_inactive_valid_count <> 0 THEN
    RAISE EXCEPTION 'Coupon validation did not respect active-only RLS visibility';
  END IF;
END;
$coupon_rls$;
RESET ROLE;

-- The staff-only SELECT path must be PERMISSIVE, not RESTRICTIVE, otherwise
-- authenticated customers would lose access to active public coupons.
DO $coupon_policy_metadata$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_policies p
     WHERE p.schemaname = 'public'
       AND p.tablename = 'coupons'
       AND p.policyname = 'Staff coupon select permission'
       AND p.permissive = 'PERMISSIVE'
       AND p.cmd = 'SELECT'
       AND 'authenticated' = ANY(p.roles)
  ) THEN
    RAISE EXCEPTION 'Staff coupon SELECT policy is not permissive';
  END IF;
END;
$coupon_policy_metadata$;

-- A normal signed-in buyer must validate active coupons, while a staff member
-- retains access to inactive coupon rows for dashboard administration.
SET ROLE authenticated;
DO $authenticated_coupon_rls$
DECLARE
  v_active_valid integer;
  v_inactive_valid integer;
  v_staff_visible integer;
BEGIN
  SELECT count(*) INTO v_active_valid
    FROM public.validate_coupon('ACTIVE10', 100)
   WHERE valid IS TRUE;

  SELECT count(*) INTO v_inactive_valid
    FROM public.validate_coupon('INACTIVE10', 100)
   WHERE valid IS TRUE;

  IF v_active_valid <> 1 OR v_inactive_valid <> 0 THEN
    RAISE EXCEPTION 'Authenticated customer coupon validation did not preserve active-only access';
  END IF;

  PERFORM set_config(
    'request.jwt.claim.sub',
    '10000000-0000-4000-8000-000000000099',
    false
  );

  SELECT count(*) INTO v_staff_visible FROM public.coupons;
  IF v_staff_visible <> 2 THEN
    RAISE EXCEPTION 'Authorized staff lost access to inactive coupons';
  END IF;
END;
$authenticated_coupon_rls$;
RESET ROLE;
