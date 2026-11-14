-- Synthetic local-only shipping configuration. No real customer or address data.
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
