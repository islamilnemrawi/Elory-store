-- Elory database security hardening.
-- Preserves existing public RPC names and role access while moving privileged
-- SECURITY DEFINER implementations into the non-exposed private schema.
-- Apply only after running the matching security fixture/integration tests.

BEGIN;

DO $security_hardening$
DECLARE
  v_targets text[] := ARRAY[
    'admin_apply_shipping_governorate_price',
    'admin_delete_order',
    'admin_delete_shipping_center',
    'admin_get_my_staff_profile',
    'admin_grant_prime_by_email',
    'admin_list_orders',
    'admin_list_prime_subscriptions',
    'admin_list_shipping',
    'admin_list_staff',
    'admin_save_shipping_center',
    'admin_save_shipping_governorate',
    'admin_set_prime_subscription_active',
    'admin_set_staff_active',
    'admin_update_order_status',
    'admin_upsert_staff_by_email',
    'elora_admin_allowed',
    'get_customer_orders',
    'get_my_prime_status',
    'has_staff_permission',
    'is_elora_staff',
    'redeem_coupon',
    'register_dashboard_push_device'
  ];
  v_count integer;
  r record;
  v_source text;
  v_identity_args text;
  v_declarations text;
  v_result text;
  v_call_args text;
  v_body text;
  v_volatility text;
  v_parallel text;
  v_strict text;
  v_anon boolean;
  v_authenticated boolean;
  v_service_role boolean;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
     OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated')
     OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role')
     OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
    RAISE EXCEPTION 'Elory security migration stopped: required Supabase API roles are missing';
  END IF;

  CREATE SCHEMA IF NOT EXISTS private;

  -- private must remain outside PostgREST exposed schemas. Refuse to proceed
  -- if a project-level or authenticator-level setting explicitly exposes it.
  IF EXISTS (
    SELECT 1
      FROM pg_db_role_setting s
      CROSS JOIN LATERAL unnest(s.setconfig) AS setting(config)
     WHERE (s.setrole = 0 OR s.setrole = 'authenticator'::regrole)
       AND setting.config LIKE 'pgrst.db_schemas=%'
       AND setting.config ILIKE '%private%'
  ) THEN
    RAISE EXCEPTION 'Elory security migration stopped: private appears in pgrst.db_schemas; remove it from Exposed Schemas first';
  END IF;

  SELECT count(*)
    INTO v_count
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
   WHERE n.nspname = 'public'
     AND p.prokind = 'f'
     AND p.prosecdef IS TRUE
     AND p.proname = ANY (v_targets);

  IF v_count <> cardinality(v_targets) THEN
    RAISE EXCEPTION
      'Elory security migration stopped: expected % SECURITY DEFINER RPCs in public, found %',
      cardinality(v_targets), v_count;
  END IF;

  -- Do not move a function unless its existing body has the appropriate
  -- identity/ownership gate. This prevents silently wrapping an unguarded RPC.
  FOR r IN
    SELECT p.oid, p.proname
      FROM pg_proc p
      JOIN pg_namespace n ON n.oid = p.pronamespace
     WHERE n.nspname = 'public'
       AND p.prokind = 'f'
       AND p.prosecdef IS TRUE
       AND p.proname = ANY (v_targets)
  LOOP
    v_source := lower(pg_get_functiondef(r.oid));

    IF r.proname LIKE 'admin_%'
       AND r.proname <> 'admin_get_my_staff_profile'
       AND position('has_staff_permission' IN v_source) = 0 THEN
      RAISE EXCEPTION 'Elory security migration stopped: % has no staff-permission guard', r.proname;
    END IF;

    IF r.proname IN (
      'admin_get_my_staff_profile',
      'elora_admin_allowed',
      'get_my_prime_status',
      'has_staff_permission',
      'is_elora_staff',
      'register_dashboard_push_device'
    ) AND position('auth.uid()' IN v_source) = 0 THEN
      RAISE EXCEPTION 'Elory security migration stopped: % has no auth.uid() ownership check', r.proname;
    END IF;

    IF r.proname IN ('get_customer_orders', 'redeem_coupon')
       AND (
         position('auth.uid()' IN v_source) = 0
         OR position('length(trim(p_access_token)) >= 24' IN v_source) = 0
       ) THEN
      RAISE EXCEPTION 'Elory security migration stopped: % has no verified user or long access-token gate', r.proname;
    END IF;

    IF has_function_privilege('public', r.oid, 'EXECUTE') THEN
      RAISE EXCEPTION 'Elory security migration stopped: % is executable by PUBLIC; review its grants first', r.proname;
    END IF;
  END LOOP;

  -- Transfer the original SECURITY DEFINER implementation without changing
  -- its body/OID. Existing RLS policy dependencies therefore remain attached
  -- to the same function object. A SECURITY INVOKER wrapper keeps the public
  -- PostgREST RPC name and signature unchanged.
  FOR r IN
    SELECT
      p.oid,
      p.proname,
      pg_get_function_identity_arguments(p.oid) AS identity_args,
      pg_get_function_arguments(p.oid) AS declarations,
      pg_get_function_result(p.oid) AS result_type,
      p.pronargs,
      p.proretset,
      p.provolatile,
      p.proisstrict,
      p.proparallel
    FROM pg_proc p
    JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public'
      AND p.prokind = 'f'
      AND p.prosecdef IS TRUE
      AND p.proname = ANY (v_targets)
    ORDER BY p.proname
  LOOP
    IF EXISTS (
      SELECT 1
        FROM pg_proc x
        JOIN pg_namespace xn ON xn.oid = x.pronamespace
       WHERE xn.nspname = 'private'
         AND x.proname = r.proname
         AND x.proargtypes = (SELECT p.proargtypes FROM pg_proc p WHERE p.oid = r.oid)
    ) THEN
      RAISE EXCEPTION 'Elory security migration stopped: private.%(...) already exists', r.proname;
    END IF;

    v_anon := has_function_privilege('anon', r.oid, 'EXECUTE');
    v_authenticated := has_function_privilege('authenticated', r.oid, 'EXECUTE');
    v_service_role := has_function_privilege('service_role', r.oid, 'EXECUTE');

    v_call_args := '';
    IF r.pronargs > 0 THEN
      SELECT string_agg('$' || arg_position::text, ', ' ORDER BY arg_position)
        INTO v_call_args
        FROM generate_series(1, r.pronargs) AS arg_position;
    END IF;

    v_volatility := CASE r.provolatile
      WHEN 'i' THEN 'IMMUTABLE'
      WHEN 's' THEN 'STABLE'
      ELSE 'VOLATILE'
    END;
    v_parallel := CASE r.proparallel
      WHEN 's' THEN 'SAFE'
      WHEN 'r' THEN 'RESTRICTED'
      ELSE 'UNSAFE'
    END;
    v_strict := CASE WHEN r.proisstrict THEN 'STRICT' ELSE 'CALLED ON NULL INPUT' END;

    IF r.proretset THEN
      v_body := format('SELECT * FROM private.%I(%s)', r.proname, v_call_args);
    ELSE
      v_body := format('SELECT private.%I(%s)', r.proname, v_call_args);
    END IF;

    EXECUTE format(
      'ALTER FUNCTION public.%I(%s) SET SCHEMA private',
      r.proname,
      r.identity_args
    );

    -- Empty search_path protects the privileged implementation from object
    -- shadowing. All application objects in these functions are schema-qualified.
    EXECUTE format(
      'ALTER FUNCTION private.%I(%s) SET search_path TO pg_catalog,
      r.proname,
      r.identity_args
    );

    EXECUTE format(
      'REVOKE ALL ON FUNCTION private.%I(%s) FROM PUBLIC, anon, authenticated, service_role',
      r.proname,
      r.identity_args
    );

    v_declarations := r.declarations;
    v_result := r.result_type;

    EXECUTE format(
      'CREATE FUNCTION public.%I(%s) RETURNS %s LANGUAGE sql %s PARALLEL %s %s SECURITY INVOKER SET search_path TO pg_catalog AS %L',
      r.proname,
      v_declarations,
      v_result,
      v_volatility,
      v_parallel,
      v_strict,
      v_body
    );

    EXECUTE format(
      'REVOKE ALL ON FUNCTION public.%I(%s) FROM PUBLIC, anon, authenticated, service_role',
      r.proname,
      r.identity_args
    );

    -- Preserve only the direct role grants that existed before migration.
    IF v_anon THEN
      EXECUTE format('GRANT EXECUTE ON FUNCTION private.%I(%s) TO anon', r.proname, r.identity_args);
      EXECUTE format('GRANT EXECUTE ON FUNCTION public.%I(%s) TO anon', r.proname, r.identity_args);
    END IF;
    IF v_authenticated THEN
      EXECUTE format('GRANT EXECUTE ON FUNCTION private.%I(%s) TO authenticated', r.proname, r.identity_args);
      EXECUTE format('GRANT EXECUTE ON FUNCTION public.%I(%s) TO authenticated', r.proname, r.identity_args);
    END IF;
    IF v_service_role THEN
      EXECUTE format('GRANT EXECUTE ON FUNCTION private.%I(%s) TO service_role', r.proname, r.identity_args);
      EXECUTE format('GRANT EXECUTE ON FUNCTION public.%I(%s) TO service_role', r.proname, r.identity_args);
    END IF;
  END LOOP;

  -- RLS policies that refer to the moved helper functions retain their function
  -- OIDs; authenticated must therefore retain private schema usage and execute
  -- on the exact original helper functions.
  GRANT USAGE ON SCHEMA private TO anon, authenticated, service_role;
END;
$security_hardening$;

-- Coupon validation only reads active coupon rows, which are already exposed
-- by the public SELECT policy. SECURITY INVOKER makes that RLS policy effective
-- and prevents this read-only API from bypassing it.
DO $coupon_validation$
BEGIN
  IF NOT EXISTS (
    SELECT 1
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
     WHERE n.nspname = 'public'
       AND c.relname = 'coupons'
       AND c.relrowsecurity IS TRUE
  ) THEN
    RAISE EXCEPTION 'Elory security migration stopped: public.coupons must have RLS enabled';
  END IF;

  IF NOT EXISTS (
    SELECT 1
      FROM pg_policies p
     WHERE p.schemaname = 'public'
       AND p.tablename = 'coupons'
       AND p.cmd IN ('SELECT', 'ALL')
       AND p.roles::text ILIKE '%anon%'
       AND coalesce(p.qual, '') ILIKE '%active%'
  ) THEN
    RAISE EXCEPTION 'Elory security migration stopped: active-only anon coupon SELECT policy was not found';
  END IF;

  IF to_regprocedure('public.validate_coupon(text,numeric)') IS NULL THEN
    RAISE EXCEPTION 'Elory security migration stopped: public.validate_coupon(text,numeric) is missing';
  END IF;
END;
$coupon_validation$;

ALTER FUNCTION public.validate_coupon(text, numeric) SECURITY INVOKER;
ALTER FUNCTION public.validate_coupon(text, numeric) SET search_path TO pg_catalog;
REVOKE ALL ON FUNCTION public.validate_coupon(text, numeric) FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.validate_coupon(text, numeric) TO anon, authenticated;

-- These privileges are not used by PostgREST and are not protected by RLS.
-- Keep normal row-level grants and all existing RLS policies unchanged.
REVOKE TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA public
  FROM anon, authenticated;

-- PostgreSQL 17 added the MAINTAIN table privilege.
DO $maintain_privilege$
BEGIN
  IF current_setting('server_version_num')::integer >= 170000 THEN
    EXECUTE 'REVOKE MAINTAIN ON ALL TABLES IN SCHEMA public FROM anon, authenticated';
    EXECUTE 'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public REVOKE MAINTAIN ON TABLES FROM anon, authenticated';
  END IF;
END;
$maintain_privilege$;

-- Prevent postgres-owned future public objects from re-acquiring the same
-- non-Data-API table privileges or default PUBLIC function execution.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE TRUNCATE, REFERENCES, TRIGGER ON TABLES FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE EXECUTE ON FUNCTIONS FROM anon, authenticated;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres
  REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC;

-- Private push configuration remains intentionally inaccessible to API roles.
DO $private_push_config$
BEGIN
  IF to_regclass('private.elora_push_config') IS NOT NULL THEN
    EXECUTE 'ALTER TABLE private.elora_push_config ENABLE ROW LEVEL SECURITY';
    EXECUTE 'REVOKE ALL ON TABLE private.elora_push_config FROM PUBLIC, anon, authenticated';
  END IF;
END;
$private_push_config$;

NOTIFY pgrst, 'reload schema';

COMMIT;
