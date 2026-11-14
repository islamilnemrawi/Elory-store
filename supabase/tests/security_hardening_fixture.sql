-- Disposable PostgreSQL 17 fixture for security_hardening migration CI.
-- This is synthetic structure only; no production rows or credentials.

DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role NOLOGIN BYPASSRLS; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN CREATE ROLE authenticator NOLOGIN; END IF;
END;
$roles$;

CREATE SCHEMA IF NOT EXISTS auth;
CREATE SCHEMA IF NOT EXISTS private;

CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$$;

CREATE OR REPLACE FUNCTION auth.role()
RETURNS text
LANGUAGE sql
STABLE
AS $$
  SELECT coalesce(nullif(current_setting('request.jwt.claim.role', true), ''), current_user::text);
$$;

ALTER DEFAULT PRIVILEGES FOR ROLE postgres
  GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT TRUNCATE, REFERENCES, TRIGGER ON TABLES TO anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  GRANT EXECUTE ON FUNCTIONS TO anon, authenticated;

CREATE TABLE public.coupons (
  id uuid PRIMARY KEY,
  code text NOT NULL,
  active boolean NOT NULL DEFAULT true,
  discount_type text NOT NULL DEFAULT 'fixed',
  discount_value numeric NOT NULL DEFAULT 10,
  max_discount numeric,
  free_shipping boolean NOT NULL DEFAULT false
);
ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;
CREATE POLICY "fixture active coupons only"
  ON public.coupons FOR SELECT TO anon, authenticated
  USING (active IS TRUE);
GRANT SELECT ON public.coupons TO anon, authenticated;
INSERT INTO public.coupons(id, code, active, discount_value)
VALUES
  ('10000000-0000-4000-8000-000000000001', 'ACTIVE10', true, 10),
  ('10000000-0000-4000-8000-000000000002', 'INACTIVE10', false, 10);

CREATE TABLE public.security_fixture_privilege_probe(id integer PRIMARY KEY);
ALTER TABLE public.security_fixture_privilege_probe ENABLE ROW LEVEL SECURITY;
GRANT SELECT, TRUNCATE, REFERENCES, TRIGGER ON public.security_fixture_privilege_probe TO anon, authenticated;

CREATE TABLE public.security_fixture_policy_probe(id integer PRIMARY KEY);
ALTER TABLE public.security_fixture_policy_probe ENABLE ROW LEVEL SECURITY;
GRANT SELECT ON public.security_fixture_policy_probe TO authenticated;
INSERT INTO public.security_fixture_policy_probe VALUES (1);

CREATE OR REPLACE FUNCTION public.has_staff_permission(p_permission text)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
  SELECT auth.uid() IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION public.elora_admin_allowed()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
  SELECT auth.uid() IS NOT NULL;
$$;

CREATE OR REPLACE FUNCTION public.get_my_prime_status()
RETURNS jsonb
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
  SELECT jsonb_build_object('active', auth.uid() IS NOT NULL);
$$;

CREATE OR REPLACE FUNCTION public.is_elora_staff()
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
  SELECT auth.uid() IS NOT NULL;
$$;

CREATE POLICY "fixture staff-only policy"
  ON public.security_fixture_policy_probe FOR SELECT TO authenticated
  USING (public.has_staff_permission('fixture.view'));

DO $admin_functions$
DECLARE
  r record;
  v_body text;
BEGIN
  FOR r IN
    SELECT *
    FROM (VALUES
      ('admin_apply_shipping_governorate_price', 'p_governorate text, p_price numeric', 'jsonb', 'shipping.manage', 'RETURN jsonb_build_object(''ok'', true);'),
      ('admin_delete_order', 'p_order_id uuid', 'boolean', 'orders.delete', 'RETURN false;'),
      ('admin_delete_shipping_center', 'p_id text', 'boolean', 'shipping.manage', 'RETURN false;'),
      ('admin_list_orders', 'p_limit integer DEFAULT 500', 'SETOF jsonb', 'orders.view', 'RETURN;'),
      ('admin_list_prime_subscriptions', '', 'SETOF jsonb', 'prime.manage', 'RETURN;'),
      ('admin_list_shipping', '', 'jsonb', 'shipping.view', 'RETURN ''{}''::jsonb;'),
      ('admin_list_staff', '', 'SETOF jsonb', 'staff.manage', 'RETURN;'),
      ('admin_save_shipping_center', 'p_id text DEFAULT '''', p_governorate text DEFAULT '''', p_center text DEFAULT '''', p_price numeric DEFAULT 0, p_active boolean DEFAULT true', 'jsonb', 'shipping.manage', 'RETURN ''{}''::jsonb;'),
      ('admin_save_shipping_governorate', 'p_governorate text, p_price numeric, p_active boolean DEFAULT true, p_centers_enabled boolean DEFAULT true', 'jsonb', 'shipping.manage', 'RETURN ''{}''::jsonb;'),
      ('admin_set_prime_subscription_active', 'p_subscription_id uuid, p_active boolean', 'jsonb', 'prime.manage', 'RETURN ''{}''::jsonb;'),
      ('admin_set_staff_active', 'p_staff_id uuid, p_active boolean', 'jsonb', 'staff.manage', 'RETURN ''{}''::jsonb;'),
      ('admin_update_order_status', 'p_order_id uuid, p_status text', 'jsonb', 'orders.edit', 'RETURN ''{}''::jsonb;'),
      ('admin_upsert_staff_by_email', 'p_email text, p_name text DEFAULT NULL, p_role text DEFAULT ''staff'', p_permissions jsonb DEFAULT ''{}''::jsonb, p_active boolean DEFAULT true', 'jsonb', 'staff.manage', 'RETURN ''{}''::jsonb;')
    ) AS x(function_name, declarations, result_type, permission_name, return_body)
  LOOP
    v_body := format(
      'BEGIN IF NOT public.has_staff_permission(%L) THEN RAISE EXCEPTION ''fixture staff access denied''; END IF; %s END;',
      r.permission_name,
      r.return_body
    );
    EXECUTE format(
      'CREATE FUNCTION public.%I(%s) RETURNS %s LANGUAGE plpgsql SECURITY DEFINER SET search_path TO pg_catalog AS %L',
      r.function_name,
      r.declarations,
      r.result_type,
      v_body
    );
  END LOOP;
END;
$admin_functions$;

CREATE OR REPLACE FUNCTION public.admin_get_my_staff_profile()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $$
BEGIN
  IF auth.uid() IS NULL THEN RETURN NULL; END IF;
  RETURN '{}'::jsonb;
END;
$$;

CREATE OR REPLACE FUNCTION public.admin_grant_prime_by_email(p_email text, p_days integer DEFAULT 30)
RETURNS TABLE(success boolean, user_id uuid, expires_at timestamptz, message text)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $$
BEGIN
  IF NOT public.has_staff_permission('prime.manage') THEN
    RETURN QUERY SELECT false, NULL::uuid, NULL::timestamptz, 'denied'::text;
    RETURN;
  END IF;
  RETURN QUERY SELECT true, NULL::uuid, NULL::timestamptz, 'ok'::text;
END;
$$;

CREATE OR REPLACE FUNCTION public.get_customer_orders(
  p_access_token text DEFAULT NULL,
  p_phone text DEFAULT NULL
)
RETURNS TABLE(
  id uuid, order_number text, user_id uuid, created_at timestamptz,
  status text, items jsonb, shipping_cost numeric, total numeric,
  governorate text, center text
)
LANGUAGE plpgsql
STABLE
SECURITY DEFINER
SET search_path TO ''
AS $$
BEGIN
  IF auth.uid() IS NULL
     AND NOT (p_access_token IS NOT NULL AND length(trim(p_access_token)) >= 24) THEN
    RETURN;
  END IF;
  RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION public.redeem_coupon(
  p_coupon_id uuid,
  p_order_id uuid DEFAULT NULL,
  p_access_token text DEFAULT NULL
)
RETURNS boolean
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO ''
AS $$
BEGIN
  IF auth.role() <> 'service_role'
     AND NOT (
       auth.uid() IS NOT NULL
       OR (p_access_token IS NOT NULL AND length(trim(p_access_token)) >= 24)
     ) THEN
    RETURN false;
  END IF;
  RETURN true;
END;
$$;

CREATE OR REPLACE FUNCTION public.register_dashboard_push_device(
  p_token text,
  p_platform text DEFAULT 'android'
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public', 'auth'
AS $$
BEGIN
  IF auth.uid() IS NULL THEN RAISE EXCEPTION 'AUTH_REQUIRED'; END IF;
  RETURN jsonb_build_object('ok', true);
END;
$$;

CREATE OR REPLACE FUNCTION public.validate_coupon(p_code text, p_subtotal numeric)
RETURNS TABLE(
  valid boolean, id uuid, code text, discount_type text,
  discount_value numeric, max_discount numeric, free_shipping boolean, message text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO 'public'
AS $$
DECLARE
  c public.coupons%ROWTYPE;
BEGIN
  SELECT * INTO c
    FROM public.coupons AS coupon
   WHERE upper(coupon.code) = upper(trim(p_code))
     AND coupon.active IS TRUE
   LIMIT 1;

  IF NOT FOUND THEN
    RETURN QUERY SELECT false, NULL::uuid, NULL::text, NULL::text,
      NULL::numeric, NULL::numeric, false, 'not found'::text;
    RETURN;
  END IF;

  RETURN QUERY SELECT true, c.id, c.code, c.discount_type,
    c.discount_value, c.max_discount, c.free_shipping, 'ok'::text;
END;
$$;

-- Mirror the production direct grants before the hardening migration.
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.admin_apply_shipping_governorate_price(text,numeric) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_delete_order(uuid) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_delete_shipping_center(text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_get_my_staff_profile() TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_grant_prime_by_email(text,integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_list_orders(integer) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_list_prime_subscriptions() TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_list_shipping() TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_list_staff() TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_save_shipping_center(text,text,text,numeric,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_save_shipping_governorate(text,numeric,boolean,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_set_prime_subscription_active(uuid,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_set_staff_active(uuid,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_update_order_status(uuid,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.admin_upsert_staff_by_email(text,text,text,jsonb,boolean) TO authenticated;
GRANT EXECUTE ON FUNCTION public.elora_admin_allowed() TO authenticated;
GRANT EXECUTE ON FUNCTION public.get_customer_orders(text,text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.get_my_prime_status() TO authenticated;
GRANT EXECUTE ON FUNCTION public.has_staff_permission(text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.is_elora_staff() TO authenticated;
GRANT EXECUTE ON FUNCTION public.redeem_coupon(uuid,uuid,text) TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.register_dashboard_push_device(text,text) TO authenticated;
GRANT EXECUTE ON FUNCTION public.validate_coupon(text,numeric) TO anon, authenticated;
