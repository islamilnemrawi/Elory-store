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
  'https://placehold.co/640x640/webp?text=Elory+Synthetic',
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
  jsonb_build_array('https://placehold.co/640x640/webp?text=Elory+Synthetic'),
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
  'https://placehold.co/640x640/webp?text=Elory+Race',
  'Synthetic Jewelry',
  100, 120, 40, 'ELORY-LOAD-RACE-CODE', 1, 0, false, true, now(),
  '[]'::jsonb, '[]'::jsonb, NULL, 'ELORY-LOAD-RACE', 0.1,
  jsonb_build_array('https://placehold.co/640x640/webp?text=Elory+Race'),
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
