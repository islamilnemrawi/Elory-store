-- Disposable CI-only schema baseline for Elory prelaunch tests.
-- This file intentionally contains schema only: no production rows, secrets, or customer data.
-- Keep the definitions aligned with the live public.products, public.orders,
-- public.shipping_governorates, and public.shipping_centers table columns.

CREATE SCHEMA IF NOT EXISTS extensions;

DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN BYPASSRLS;
  END IF;
END;
$roles$;

DO $extensions$
DECLARE
  v_schema text;
BEGIN
  SELECT n.nspname INTO v_schema
  FROM pg_extension e
  JOIN pg_namespace n ON n.oid = e.extnamespace
  WHERE e.extname = 'pgcrypto';

  IF v_schema IS NULL THEN
    EXECUTE 'CREATE EXTENSION pgcrypto WITH SCHEMA extensions';
  ELSIF v_schema <> 'extensions' THEN
    EXECUTE 'ALTER EXTENSION pgcrypto SET SCHEMA extensions';
  END IF;
END;
$extensions$;

CREATE TABLE public.products (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  image text,
  category text,
  price numeric NOT NULL DEFAULT 0,
  old_price numeric DEFAULT 0,
  wholesale_price numeric DEFAULT 0,
  code text,
  stock integer NOT NULL DEFAULT 0,
  discount numeric DEFAULT 0,
  featured boolean NOT NULL DEFAULT false,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  colors jsonb,
  sizes jsonb,
  variants jsonb,
  sku text,
  weight numeric,
  gallery jsonb,
  color_options jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE public.orders (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  order_number bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  customer_name text,
  phone text,
  governorate text,
  center text,
  address text,
  notes text,
  items jsonb NOT NULL DEFAULT '[]'::jsonb,
  subtotal numeric DEFAULT 0,
  shipping_cost numeric DEFAULT 0,
  total numeric DEFAULT 0,
  payment_method text,
  status text NOT NULL DEFAULT 'جديد',
  prime boolean NOT NULL DEFAULT false,
  profit numeric DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  coupon_code text,
  coupon_discount numeric NOT NULL DEFAULT 0,
  coupon_free_shipping boolean NOT NULL DEFAULT false,
  customer_user_id uuid,
  user_id uuid,
  customer_access_token text,
  prime_discount numeric DEFAULT 0,
  prime_free_shipping boolean DEFAULT false,
  coupon_redeemed_at timestamptz,
  prime_requested boolean NOT NULL DEFAULT false
);

CREATE TABLE public.shipping_governorates (
  governorate text PRIMARY KEY,
  price numeric NOT NULL DEFAULT 0,
  centers_enabled boolean NOT NULL DEFAULT true,
  active boolean NOT NULL DEFAULT true,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.shipping_centers (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  governorate text NOT NULL,
  center text,
  price numeric NOT NULL DEFAULT 0,
  active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipping_governorates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.shipping_centers ENABLE ROW LEVEL SECURITY;

GRANT SELECT ON public.products TO anon, authenticated;
GRANT SELECT ON public.shipping_governorates TO anon, authenticated;
GRANT SELECT ON public.shipping_centers TO anon, authenticated;

CREATE POLICY local_prelaunch_products_read
  ON public.products FOR SELECT TO anon, authenticated
  USING (active IS TRUE);

CREATE POLICY local_prelaunch_governorates_read
  ON public.shipping_governorates FOR SELECT TO anon, authenticated
  USING (active IS TRUE);

CREATE POLICY local_prelaunch_centers_read
  ON public.shipping_centers FOR SELECT TO anon, authenticated
  USING (active IS TRUE);
