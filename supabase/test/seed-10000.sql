INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('elory-load-test', 'elory-load-test', true, 1048576, ARRAY['image/png'])
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

BEGIN;

-- Re-running the seed is safe: remove only clearly marked local fixtures first.
INSERT INTO public.shipping_governorates (governorate, price, centers_enabled, active)
VALUES ('ELORY LOAD TEST', 25, true, true)
ON CONFLICT (governorate) DO UPDATE
SET price = EXCLUDED.price,
    centers_enabled = EXCLUDED.centers_enabled,
    active = EXCLUDED.active,
    updated_at = now();

DELETE FROM public.shipping_centers
WHERE governorate = 'ELORY LOAD TEST';
INSERT INTO public.shipping_centers (governorate, center, price, active)
VALUES ('ELORY LOAD TEST', 'LOCAL TEST CENTER', 25, true);

DELETE FROM public.orders
 WHERE notes LIKE 'ELORY_LOAD_TEST:%';
DELETE FROM public.products
 WHERE sku LIKE 'ELORY-LOAD-%';

INSERT INTO public.products (
  name, description, image, category, price, old_price, wholesale_price,
  code, stock, discount, featured, active, created_at,
  colors, sizes, variants, sku, weight, gallery, color_options
)
SELECT
  'Elory Synthetic Jewelry ' || lpad(g::text, 5, '0'),
  'Synthetic local load-test catalog row. Not a real product.',
  'http://127.0.0.1:54321/storage/v1/object/public/elory-load-test/product.png',
  'Synthetic Jewelry',
  100 + (g % 300),
  130 + (g % 300),
  40 + (g % 100),
  'ELORY-LOAD-CODE-' || lpad(g::text, 5, '0'),
  CASE WHEN g = 1 THEN 1000000 ELSE 1000 END,
  0,
  false,
  true,
  now() - (g * interval '1 second'),
  '[]'::jsonb,
  '[]'::jsonb,
  NULL,
  'ELORY-LOAD-' || lpad(g::text, 5, '0'),
  0.1,
  jsonb_build_array('http://127.0.0.1:54321/storage/v1/object/public/elory-load-test/product.png'),
  '[]'::jsonb
FROM generate_series(1, 10000) AS g;

INSERT INTO public.products (
  name, description, image, category, price, old_price, wholesale_price,
  code, stock, discount, featured, active, created_at,
  colors, sizes, variants, sku, weight, gallery, color_options
)
VALUES (
  'Elory Synthetic Stock Race Fixture',
  'One-unit concurrency fixture. Synthetic local test only.',
  'http://127.0.0.1:54321/storage/v1/object/public/elory-load-test/product.png',
  'Synthetic Jewelry',
  100, 120, 40, 'ELORY-LOAD-RACE-CODE', 1, 0, false, true, now(),
  '[]'::jsonb, '[]'::jsonb, NULL, 'ELORY-LOAD-RACE', 0.1,
  jsonb_build_array('http://127.0.0.1:54321/storage/v1/object/public/elory-load-test/product.png'),
  '[]'::jsonb
);

DO $$
DECLARE
  v_count integer;
BEGIN
  SELECT count(*) INTO v_count
    FROM public.products
   WHERE sku LIKE 'ELORY-LOAD-%';
  IF v_count <> 10001 THEN
    RAISE EXCEPTION 'Expected 10001 synthetic products, found %.', v_count;
  END IF;
END;
$$;

COMMIT;
