DO $roles$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN BYPASSRLS; END IF;
END;
$roles$;

CREATE SCHEMA auth;
CREATE OR REPLACE FUNCTION auth.uid()
RETURNS uuid
LANGUAGE sql
STABLE
AS $function$
  SELECT nullif(current_setting('request.jwt.claim.sub', true), '')::uuid;
$function$;
GRANT USAGE ON SCHEMA auth TO anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated, service_role;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

CREATE TABLE public.orders (
  id uuid PRIMARY KEY,
  order_number text,
  user_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  status text,
  payment_method text,
  items jsonb NOT NULL DEFAULT '[]'::jsonb,
  shipping_cost numeric,
  total numeric,
  governorate text,
  center text,
  customer_order_code text,
  customer_access_token text
);
ALTER TABLE public.orders ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.orders FROM anon, authenticated;

INSERT INTO public.orders (
  id, order_number, user_id, created_at, status, payment_method,
  items, shipping_cost, total, governorate, center, customer_order_code,
  customer_access_token
)
VALUES
(
  '11111111-1111-4111-8111-111111111111', 'ORD-COD', NULL, now()-interval '2 days',
  'تم تأكيد الطلب', 'cash_on_delivery',
  jsonb_build_array(jsonb_build_object(
    'product_id','aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',
    'name','Test product','product_name','Internal product name',
    'image','https://example.test/public.webp','product_image','https://example.test/internal.webp',
    'code','ELORY-CODE-1','product_code','INTERNAL-CODE','sku','INTERNAL-SKU',
    'wholesale_price',40,'cost_price',30,'profit',70,
    'price',100,'quantity',1,'size','M','color','Red','color_hex','#ff0000'
  )),
  20, 120, 'القاهرة', 'وسط البلد', 'ELORY-ORDER-COD',
  'guest-token-12345678901234567890'
),
(
  '22222222-2222-4222-8222-222222222222', 'ORD-PAID', NULL, now()-interval '1 day',
  'تم التسليم', 'card',
  jsonb_build_array(jsonb_build_object(
    'product_id','bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb',
    'name','Paid product','product_name','Internal product name',
    'image','https://example.test/public.webp','product_image','https://example.test/internal.webp',
    'code','ELORY-CODE-2','product_code','INTERNAL-CODE','sku','INTERNAL-SKU',
    'wholesale_price',50,'cost_price',35,'profit',65,
    'price',150,'quantity',1,'size','L','color','Blue','color_hex','#0000ff'
  )),
  20, 170, 'الجيزة', 'الدقي', 'ELORY-ORDER-PAID',
  'guest-token-12345678901234567890'
),
(
  '33333333-3333-4333-8333-333333333333', 'ORD-AUTH', 'aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa', now(),
  'تم تأكيد الطلب', 'cash_on_delivery',
  '[{"name":"Auth product","code":"AUTH-CODE","price":50,"quantity":1}]'::jsonb,
  10, 60, 'القاهرة', 'مدينة نصر', 'ELORY-ORDER-AUTH',
  'auth-only-token-12345678901234567890'
);

INSERT INTO public.orders (
  id, order_number, status, payment_method, items, shipping_cost, total,
  customer_order_code, customer_access_token
)
SELECT
  gen_random_uuid(),
  'ORD-HIDDEN-' || row_number() OVER (),
  s.status,
  s.payment_method,
  '[{"name":"Hidden product","code":"ELORY-CODE","product_code":"INTERNAL","sku":"INTERNAL-SKU","wholesale_price":20,"price":100,"quantity":1}]'::jsonb,
  0, 100, 'ELORY-HIDDEN', 'guest-token-12345678901234567890'
FROM (VALUES
  ('جاري الدفع','card'),
  ('فشل الدفع','card'),
  ('فشل إنشاء الدفع','card'),
  ('payment pending','card'),
  ('pending payment','card'),
  ('payment failed','card'),
  ('failed payment','card'),
  ('failed to create payment','card'),
  ('جديد','card'),
  ('جاري التأكيد','card'),
  ('pending','card'),
  ('new','vodafone_cash')
) AS s(status,payment_method);
