INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES ('elory-load-test', 'elory-load-test', true, 1048576, ARRAY['image/png'])
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    public = EXCLUDED.public,
    file_size_limit = EXCLUDED.file_size_limit,
    allowed_mime_types = EXCLUDED.allowed_mime_types;

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
