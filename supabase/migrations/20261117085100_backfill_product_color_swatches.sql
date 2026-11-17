-- Convert legacy textual product colors to structured swatches once.
-- Keep public.products.colors unchanged for compatibility with older storefronts and existing order labels.
WITH legacy_swatches AS (
    SELECT
        p.id,
        pg_catalog.jsonb_agg(
            pg_catalog.jsonb_build_object(
                'name', pg_catalog.btrim(c.value),
                'hex',
                CASE
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('احمر','أحمر','red') THEN '#DC2626'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('اسود','أسود','black') THEN '#171717'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('ازرق','أزرق','blue') THEN '#2563EB'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('كحلي','navy') THEN '#1E3A8A'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('اخضر','أخضر','green') THEN '#16A34A'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('اصفر','أصفر','yellow') THEN '#EAB308'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('وردي','pink') THEN '#EC4899'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('موف','mauve') THEN '#8B5CF6'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('بنفسجي','purple') THEN '#6D4CBB'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('عنابي','نبيتي','burgundy','maroon') THEN '#7F1D3A'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('بيج','beige') THEN '#D6C2A1'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('بني','brown') THEN '#8B5E3C'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('ذهبي','gold') THEN '#C7A04A'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('فضي','silver','رمادي','gray','grey') THEN '#9CA3AF'
                    WHEN pg_catalog.lower(pg_catalog.btrim(c.value)) IN ('ابيض','أبيض','white','اوف وايت','off white') THEN '#F8FAFC'
                    ELSE '#8E7A85'
                END
            )
            ORDER BY c.ordinality
        ) AS options
    FROM public.products AS p
    CROSS JOIN LATERAL pg_catalog.jsonb_array_elements_text(
        CASE
            WHEN pg_catalog.jsonb_typeof(p.colors) = 'array' THEN p.colors
            ELSE '[]'::jsonb
        END
    ) WITH ORDINALITY AS c(value, ordinality)
    WHERE pg_catalog.jsonb_typeof(p.colors) = 'array'
      AND pg_catalog.jsonb_array_length(p.colors) > 0
      AND (
          p.color_options IS NULL
          OR p.color_options = '[]'::jsonb
      )
      AND pg_catalog.btrim(c.value) <> ''
    GROUP BY p.id
)
UPDATE public.products AS p
SET color_options = legacy_swatches.options
FROM legacy_swatches
WHERE p.id = legacy_swatches.id
  AND (
      p.color_options IS NULL
      OR p.color_options = '[]'::jsonb
  );
